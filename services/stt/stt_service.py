# services/stt/stt_service.py
"""Multi-provider Speech-to-Text service — dispatches to local Whisper, OpenAI-compatible API, or browser."""

import io
import logging
import httpx
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class STTService:
    """Multi-provider STT service.

    Reads provider config from data/settings.json on each call.
    Providers:
      "disabled"        — no STT
      "browser"         — client-side Web Speech API (no server transcription)
      "local"           — faster-whisper on CPU/GPU
      "local-moonshine" — Moonshine ONNX (tiny/base) on CPU (faster, English-only)
      "local-moonshine-coreml" — Moonshine CoreML (.mlpackage) on Apple Neural Engine
      "endpoint:<id>"   — OpenAI-compatible /audio/transcriptions via ModelEndpoint
    """

    def __init__(self):
        self._whisper_model = None  # lazy-init
        self._moonshine_model = None  # lazy-init
        self._moonshine_tokenizer = None
        self._moonshine_coreml_encoder = None  # lazy-init
        self._moonshine_coreml_decoder = None  # lazy-init
        self._moonshine_coreml_hf_model = None    # HF model for cross-KV projection weights
        self._moonshine_coreml_rope_tables = None  # precomputed [(cos,sin), ...] for positions 0..S_MAX-1
        self._moonshine_coreml_constants = None   # dict of NL,H,D,HID,S_MAX,rot_dim
        # moonshine-streaming-tiny CoreML artifacts
        self._moonshine_coreml_s_encoder = None
        self._moonshine_coreml_s_decoder = None
        self._moonshine_coreml_s_rope_tables = None
        self._moonshine_coreml_s_constants = None
        self._moonshine_coreml_s_kw = None
        self._moonshine_coreml_s_vw = None
        self._moonshine_coreml_s_kb = None
        self._moonshine_coreml_s_vb = None
        self._moonshine_coreml_s_pos_emb = None  # [max_pos, HID] learned cross-attn pos emb

    # ── Settings ──

    def _load_settings(self) -> dict:
        from src.settings import load_settings
        saved = load_settings()
        return {
            "stt_enabled": saved.get("stt_enabled", False),
            "stt_provider": saved.get("stt_provider", "disabled"),
            "stt_model": saved.get("stt_model", "base"),
            "stt_language": saved.get("stt_language", ""),
        }

    @property
    def available(self) -> bool:
        settings = self._load_settings()
        if settings.get("stt_enabled") is False:
            return False
        provider = settings["stt_provider"]
        if provider == "disabled":
            return False
        if provider == "browser":
            return True  # handled client-side
        if provider == "local":
            return self._get_whisper() is not None
        if provider == "local-moonshine":
            return self._get_moonshine() is not None
        if provider == "local-moonshine-coreml":
            return self._get_moonshine_coreml() is not None
        if provider == "local-moonshine-coreml-streaming":
            return self._get_moonshine_coreml_streaming() is not None
        if provider.startswith("endpoint:"):
            return True  # assume reachable
        return False

    # ── Local Whisper ──

    def _get_whisper(self):
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                logger.warning("faster-whisper not installed. Install with: pip install faster-whisper")
                return None
            try:
                settings = self._load_settings()
                model_size = settings.get("stt_model", "base")
                # faster-whisper runs on CTranslate2, not torch. torch is only
                # used (optionally) to detect a CUDA device for acceleration —
                # if it's missing or unusable we just run on CPU. Keeping this
                # probe separate (and tolerant of any failure, e.g. a broken
                # CUDA/torch install that raises OSError on import) means a
                # torch-less or torch-broken machine still does CPU
                # transcription instead of failing with a misleading
                # "faster-whisper not installed" error.
                try:
                    import torch
                    use_cuda = torch.cuda.is_available()
                except Exception:
                    use_cuda = False
                device = "cuda" if use_cuda else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"
                self._whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
                logger.info(f"faster-whisper model '{model_size}' loaded on {device}")
            except Exception as e:
                logger.error(f"Failed to load whisper model: {e}")
                return None
        return self._whisper_model

    def _transcribe_local(self, audio_bytes: bytes, language: str = "") -> Optional[str]:
        model = self._get_whisper()
        if not model:
            return None
        tmp_path = None
        try:
            # Write to temp file (faster-whisper needs a file path or file-like)
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            kwargs = {}
            if language:
                kwargs["language"] = language

            segments, info = model.transcribe(tmp_path, **kwargs)
            text = " ".join(seg.text.strip() for seg in segments)

            logger.info(f"Local STT: {len(text)} chars, lang={info.language}, prob={info.language_probability:.2f}")
            return text
        except Exception as e:
            logger.error(f"Local STT transcription failed: {e}", exc_info=True)
            return None
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    # ── Local Moonshine ──

    def _get_moonshine(self):
        """Load Moonshine ONNX model with CPU-tuned settings"""
        if self._moonshine_model is None:
            try:
                import moonshine_onnx as m
                import onnxruntime as ort
                from moonshine_onnx.model import MoonshineOnnxModel
            except ImportError:
                logger.warning("moonshine-onnx not installed. Install with: pip install useful-moonshine-onnx")
                return None
            try:
                settings = self._load_settings()
                model_size = settings.get("stt_model", "tiny")  # tiny or base

                # Create model with CPU-tuned ONNX Runtime settings
                model = MoonshineOnnxModel(model_name=model_size)

                # Tune both encoder and decoder for multi-threaded CPU
                for session_attr in ['encoder', 'decoder']:
                    sess = getattr(model, session_attr)
                    path = sess._model_path
                    opts = ort.SessionOptions()
                    opts.intra_op_num_threads = 4  # parallel ops within a layer
                    opts.inter_op_num_threads = 1  # sequential graph execution
                    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    setattr(model, session_attr, ort.InferenceSession(
                        path, opts, providers=['CPUExecutionProvider']
                    ))

                self._moonshine_model = model
                self._moonshine_tokenizer = m.load_tokenizer()
                logger.info(f"Moonshine ONNX model '{model_size}' loaded on CPU (4-thread tuned)")
            except Exception as e:
                logger.error(f"Failed to load moonshine model: {e}")
                return None
        return self._moonshine_model

    def _transcribe_moonshine(self, audio_bytes: bytes, language: str = "") -> Optional[str]:
        """Transcribe with Moonshine ONNX (English-only, fast)"""
        model = self._get_moonshine()
        if not model:
            return None
        tmp_path = None
        try:
            import moonshine_onnx as m

            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # Load audio and transcribe
            audio = m.load_audio(tmp_path)
            tokens = model.generate(audio)
            text = self._moonshine_tokenizer.decode_batch(tokens)[0]

            logger.info(f"Moonshine STT: {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"Moonshine STT transcription failed: {e}", exc_info=True)
            return None
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    # ── Local Moonshine (CoreML / Apple Neural Engine) ──

    def _get_moonshine_coreml(self):
        """Load Moonshine CoreML encoder/decoder .mlpackage files (Apple Neural Engine)"""
        if self._moonshine_coreml_encoder is None or self._moonshine_coreml_decoder is None:
            try:
                import coremltools as ct
            except ImportError:
                logger.warning("coremltools not installed. Install with: pip install coremltools")
                return None
            try:
                import os, numpy as np
                import moonshine_onnx as m

                settings = self._load_settings()
                model_size = settings.get("stt_model", "tiny")
                model_dir = os.path.expanduser(f"~/.cache/moonshine-coreml/{model_size}/")
                encoder_path = os.path.join(model_dir, "encoder.mlpackage")
                decoder_path = os.path.join(model_dir, "decoder_stateful.mlpackage")
                weights_path = os.path.join(model_dir, "cross_kv_weights.npz")
                if not (os.path.exists(encoder_path) and os.path.exists(decoder_path)):
                    logger.warning(
                        f"Moonshine CoreML packages not found in {model_dir} "
                        "(expected encoder.mlpackage and decoder_stateful.mlpackage)"
                    )
                    return None
                if not os.path.exists(weights_path):
                    logger.warning(
                        f"cross_kv_weights.npz not found in {model_dir}. "
                        "Run: python /tmp/extract_coreml_weights.py"
                    )
                    return None

                self._moonshine_coreml_encoder = ct.models.MLModel(encoder_path)
                # Stateful decoder must use CPU_ONLY — ANE rejects large stateful tensors
                self._moonshine_coreml_decoder = ct.models.MLModel(
                    decoder_path, compute_units=ct.ComputeUnit.CPU_ONLY
                )
                if self._moonshine_tokenizer is None:
                    self._moonshine_tokenizer = m.load_tokenizer()

                # Load pre-extracted weights (no HF model download at runtime)
                w = np.load(weights_path)
                NL = int(w["NL"]); H = int(w["H"]); D = int(w["D"])
                HID = int(w["HID"]); S_MAX = int(w["S_MAX"]); rot_dim = int(w["rot_dim"])
                self._moonshine_coreml_constants = {
                    "NL": NL, "H": H, "D": D, "HID": HID, "S_MAX": S_MAX, "rot_dim": rot_dim
                }

                # Cross-KV projection weights per layer [H*D, HID]
                self._moonshine_coreml_kw = [w[f"layer{i}_k_weight"] for i in range(NL)]
                self._moonshine_coreml_vw = [w[f"layer{i}_v_weight"] for i in range(NL)]
                self._moonshine_coreml_kb = [w.get(f"layer{i}_k_bias") for i in range(NL)]
                self._moonshine_coreml_vb = [w.get(f"layer{i}_v_bias") for i in range(NL)]

                # RoPE tables: reshape to [S_MAX, 1, 1, 1, rot_dim] for slicing
                cos_tables = w["cos_tables"]  # [S_MAX, rot_dim]
                sin_tables = w["sin_tables"]
                self._moonshine_coreml_rope_tables = [
                    (cos_tables[i].reshape(1, 1, 1, -1), sin_tables[i].reshape(1, 1, 1, -1))
                    for i in range(S_MAX)
                ]

                logger.info(f"Moonshine CoreML model '{model_size}' loaded on Apple Neural Engine")
            except Exception as e:
                logger.error(f"Failed to load moonshine CoreML model: {e}")
                self._moonshine_coreml_encoder = None
                self._moonshine_coreml_decoder = None
                self._moonshine_coreml_hf_model = None
                self._moonshine_coreml_rope_tables = None
                return None
        return self._moonshine_coreml_encoder

    def _transcribe_moonshine_coreml(self, audio_bytes: bytes, language: str = "") -> Optional[str]:
        """Transcribe with Moonshine CoreML on the Apple Neural Engine (English-only, fast)"""
        if self._get_moonshine_coreml() is None:
            return None
        encoder = self._moonshine_coreml_encoder
        decoder = self._moonshine_coreml_decoder
        consts = self._moonshine_coreml_constants
        NL = consts["NL"]; H = consts["H"]; D = consts["D"]
        HID = consts["HID"]; S_MAX = consts["S_MAX"]
        rope_tables = self._moonshine_coreml_rope_tables
        tmp_path = None
        try:
            import moonshine_onnx as m
            import numpy as np

            # Write to temp file for moonshine_onnx audio loader
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            audio = m.load_audio(tmp_path)  # float32 [1, N]

            # Pad to the fixed encoder window (10s = 160000 samples at 16kHz)
            enc_window = 160000
            if audio.shape[1] < enc_window:
                audio = np.pad(audio, ((0, 0), (0, enc_window - audio.shape[1])))
            elif audio.shape[1] > enc_window:
                audio = audio[:, :enc_window]

            # --- Encoder ---
            enc_in = list(encoder.input_description)[0]
            enc_out = list(encoder.output_description)[0]
            enc_result = encoder.predict({enc_in: audio})
            hidden_states = enc_result[enc_out]  # numpy [1, S_enc, 288]
            # Ensure shape is [1, S_enc, HID]; some exports add batch dim differently
            if hidden_states.ndim == 2:
                hidden_states = hidden_states[None]  # [1, S_enc, HID]

            # --- Precompute cross-KV (once per utterance, pure numpy) ---
            # hidden_states: [1, S_enc, HID]; weights: [H*D, HID] → matmul → [1, S_enc, H*D]
            kw = self._moonshine_coreml_kw
            vw = self._moonshine_coreml_vw
            kb = self._moonshine_coreml_kb
            vb = self._moonshine_coreml_vb
            cross_k_list, cross_v_list = [], []
            for i in range(NL):
                k = hidden_states @ kw[i].T  # [1, S_enc, H*D]
                v = hidden_states @ vw[i].T
                if kb[i] is not None:
                    k = k + kb[i]
                if vb[i] is not None:
                    v = v + vb[i]
                S_enc = k.shape[1]
                k = k.reshape(1, S_enc, H, D).transpose(0, 2, 1, 3)  # [1, H, S_enc, D]
                v = v.reshape(1, S_enc, H, D).transpose(0, 2, 1, 3)
                cross_k_list.append(k)
                cross_v_list.append(v)
            cross_k = np.stack(cross_k_list).astype(np.float32)  # [NL, 1, H, S_enc, D]
            cross_v = np.stack(cross_v_list).astype(np.float32)

            # --- Stateful decode loop ---
            # cross_k/v live in model state (set once); self_k/v updated in-place each step
            decoder_start_token_id = 1
            eos_token_id = 2
            max_tokens = min(S_MAX, 200)

            state = decoder.make_state()
            state.write_state("cross_k", cross_k)
            state.write_state("cross_v", cross_v)

            attn_mask = np.full((1, 1, 1, S_MAX), -1e4, dtype=np.float32)
            attn_mask[..., 0] = 0.0
            onehot = np.zeros((1, 1, S_MAX, 1), dtype=np.float32)
            onehot[0, 0, 0, 0] = 1.0

            tokens = [decoder_start_token_id]
            for step in range(max_tokens):
                cos, sin = rope_tables[step]
                result = decoder.predict(
                    {
                        "input_ids":    np.array([[tokens[-1]]], dtype=np.int32),
                        "attn_mask":    attn_mask,
                        "cos":          cos,
                        "sin":          sin,
                        "write_onehot": onehot,
                    },
                    state=state,
                )
                next_token = int(np.asarray(result["logits"])[0, 0].argmax())
                tokens.append(next_token)
                if next_token == eos_token_id:
                    break

                next_pos = step + 1
                if next_pos < S_MAX:
                    attn_mask[..., next_pos] = 0.0
                    onehot = np.zeros((1, 1, S_MAX, 1), dtype=np.float32)
                    onehot[0, 0, next_pos, 0] = 1.0

            text = self._moonshine_tokenizer.decode_batch([tokens])[0]
            logger.info(f"Moonshine CoreML STT: {len(text)} chars, {len(tokens)} tokens")
            return text
        except Exception as e:
            logger.error(f"Moonshine CoreML STT transcription failed: {e}", exc_info=True)
            return None
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    # ── Local Moonshine Streaming (CoreML / Apple Neural Engine) ──

    # Encoder input sizes (samples) → S_enc = size/320
    _STREAMING_ENCODER_BUCKETS = [16000, 48000, 80000, 160000]
    _STREAMING_S_ENC_MAX = 500  # decoder is exported with this fixed S_enc

    def _get_moonshine_coreml_streaming(self):
        """Load moonshine-streaming-tiny CoreML encoder/decoder."""
        if self._moonshine_coreml_s_encoder is None or self._moonshine_coreml_s_decoder is None:
            try:
                import coremltools as ct
            except ImportError:
                logger.warning("coremltools not installed")
                return None
            try:
                import os, numpy as np
                import moonshine_onnx as m

                model_dir = os.path.expanduser("~/.cache/moonshine-coreml/tiny-streaming/")
                encoder_path = os.path.join(model_dir, "encoder.mlpackage")
                decoder_path = os.path.join(model_dir, "decoder_stateful.mlpackage")
                weights_path = os.path.join(model_dir, "cross_kv_weights.npz")
                if not (os.path.exists(encoder_path) and os.path.exists(decoder_path)):
                    logger.warning(f"Moonshine streaming CoreML packages not found in {model_dir}")
                    return None
                if not os.path.exists(weights_path):
                    logger.warning(f"cross_kv_weights.npz not found in {model_dir}")
                    return None

                self._moonshine_coreml_s_encoder = ct.models.MLModel(encoder_path)
                self._moonshine_coreml_s_decoder = ct.models.MLModel(
                    decoder_path, compute_units=ct.ComputeUnit.CPU_ONLY
                )
                if self._moonshine_tokenizer is None:
                    self._moonshine_tokenizer = m.load_tokenizer()

                w = np.load(weights_path)
                NL = int(w["NL"]); H = int(w["H"]); D = int(w["D"])
                HID = int(w["HID"]); S_MAX = int(w["S_MAX"]); rot_dim = int(w["rot_dim"])
                self._moonshine_coreml_s_constants = {
                    "NL": NL, "H": H, "D": D, "HID": HID, "S_MAX": S_MAX, "rot_dim": rot_dim
                }
                self._moonshine_coreml_s_kw = [w[f"layer{i}_k_weight"] for i in range(NL)]
                self._moonshine_coreml_s_vw = [w[f"layer{i}_v_weight"] for i in range(NL)]
                self._moonshine_coreml_s_kb = [w.get(f"layer{i}_k_bias") for i in range(NL)]
                self._moonshine_coreml_s_vb = [w.get(f"layer{i}_v_bias") for i in range(NL)]
                self._moonshine_coreml_s_pos_emb = w["pos_emb_weight"]  # [max_pos, HID]

                cos_tables = w["cos_tables"]  # [S_MAX, rot_dim]
                sin_tables = w["sin_tables"]
                self._moonshine_coreml_s_rope_tables = [
                    (cos_tables[i].reshape(1, 1, 1, -1), sin_tables[i].reshape(1, 1, 1, -1))
                    for i in range(S_MAX)
                ]
                logger.info("Moonshine streaming CoreML loaded (CPU+NE encoder, CPU decoder)")
            except Exception as e:
                logger.error(f"Failed to load moonshine streaming CoreML model: {e}")
                self._moonshine_coreml_s_encoder = None
                self._moonshine_coreml_s_decoder = None
                return None
        return self._moonshine_coreml_s_encoder

    def _transcribe_moonshine_coreml_streaming(self, audio_bytes: bytes, language: str = "") -> Optional[str]:
        """Transcribe with moonshine-streaming-tiny on CoreML (English-only)."""
        if self._get_moonshine_coreml_streaming() is None:
            return None
        encoder = self._moonshine_coreml_s_encoder
        decoder = self._moonshine_coreml_s_decoder
        consts = self._moonshine_coreml_s_constants
        NL = consts["NL"]; H = consts["H"]; D = consts["D"]
        HID = consts["HID"]; S_MAX = consts["S_MAX"]
        rope_tables = self._moonshine_coreml_s_rope_tables
        S_ENC_MAX = self._STREAMING_S_ENC_MAX
        tmp_path = None
        try:
            import moonshine_onnx as m
            import numpy as np

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            audio = m.load_audio(tmp_path)  # float32 [1, N]

            # Always pad/clip to 10s so encoder output is exactly S_ENC_MAX=500 frames.
            # Variable-bucket encoding requires a decoder re-export with cross-attn masking.
            enc_window = self._STREAMING_ENCODER_BUCKETS[-1]  # 160000
            if audio.shape[1] < enc_window:
                audio = np.pad(audio, ((0, 0), (0, enc_window - audio.shape[1])))
            elif audio.shape[1] > enc_window:
                audio = audio[:, :enc_window]

            # Encoder
            enc_in = list(encoder.input_description)[0]
            enc_out = list(encoder.output_description)[0]
            hidden_states = encoder.predict({enc_in: audio})[enc_out]  # [1, 500, 320]
            if hidden_states.ndim == 2:
                hidden_states = hidden_states[None]

            # Streaming decoder adds learned positional embeddings to encoder hidden states
            # before projecting to cross-KV. Apply that here (proj is Identity so skip it).
            pos_emb = self._moonshine_coreml_s_pos_emb  # [max_pos, HID]
            S_enc_actual = hidden_states.shape[1]
            hidden_states = hidden_states + pos_emb[:S_enc_actual]  # [1, S_enc, HID]

            kw = self._moonshine_coreml_s_kw
            vw = self._moonshine_coreml_s_vw
            kb = self._moonshine_coreml_s_kb
            vb = self._moonshine_coreml_s_vb
            cross_k_list, cross_v_list = [], []
            for i in range(NL):
                k = hidden_states @ kw[i].T  # [1, S_ENC_MAX, H*D]
                v = hidden_states @ vw[i].T
                if kb[i] is not None:
                    k = k + kb[i]
                if vb[i] is not None:
                    v = v + vb[i]
                k = k.reshape(1, S_ENC_MAX, H, D).transpose(0, 2, 1, 3)
                v = v.reshape(1, S_ENC_MAX, H, D).transpose(0, 2, 1, 3)
                cross_k_list.append(k)
                cross_v_list.append(v)
            cross_k = np.stack(cross_k_list).astype(np.float32)  # [NL, 1, H, S_ENC_MAX, D]
            cross_v = np.stack(cross_v_list).astype(np.float32)

            # Stateful decode loop
            decoder_start_token_id = 1
            eos_token_id = 2
            max_tokens = min(S_MAX, 200)

            state = decoder.make_state()
            state.write_state("cross_k", cross_k)
            state.write_state("cross_v", cross_v)

            attn_mask = np.full((1, 1, 1, S_MAX), -1e4, dtype=np.float32)
            attn_mask[..., 0] = 0.0
            onehot = np.zeros((1, 1, S_MAX, 1), dtype=np.float32)
            onehot[0, 0, 0, 0] = 1.0

            tokens = [decoder_start_token_id]
            for step in range(max_tokens):
                cos, sin = rope_tables[step]
                result = decoder.predict(
                    {
                        "input_ids":    np.array([[tokens[-1]]], dtype=np.int32),
                        "attn_mask":    attn_mask,
                        "cos":          cos,
                        "sin":          sin,
                        "write_onehot": onehot,
                    },
                    state=state,
                )
                next_token = int(np.asarray(result["logits"])[0, 0].argmax())
                tokens.append(next_token)
                if next_token == eos_token_id:
                    break

                next_pos = step + 1
                if next_pos < S_MAX:
                    attn_mask[..., next_pos] = 0.0
                    onehot = np.zeros((1, 1, S_MAX, 1), dtype=np.float32)
                    onehot[0, 0, next_pos, 0] = 1.0

            text = self._moonshine_tokenizer.decode_batch([tokens])[0]
            logger.info(f"Moonshine streaming CoreML STT: {len(text)} chars, {len(tokens)} tokens")
            return text
        except Exception as e:
            logger.error(f"Moonshine streaming CoreML STT failed: {e}", exc_info=True)
            return None
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    # ── API endpoint ──

    def _transcribe_api(self, audio_bytes: bytes, endpoint_id: str, model: str, language: str = "") -> Optional[str]:
        from src.database import SessionLocal, ModelEndpoint

        db = SessionLocal()
        try:
            ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == endpoint_id).first()
            if not ep:
                logger.error(f"STT endpoint {endpoint_id} not found")
                return None
            base_url = ep.base_url.rstrip("/")
            api_key = ep.api_key
        finally:
            db.close()

        url = base_url + "/audio/transcriptions"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        files = {"file": ("audio.webm", io.BytesIO(audio_bytes), "audio/webm")}
        data = {"model": model or "whisper-1"}
        if language:
            data["language"] = language

        try:
            r = httpx.post(url, headers=headers, files=files, data=data, timeout=60)
            r.raise_for_status()
            result = r.json()
            text = result.get("text", "")
            logger.info(f"API STT: {len(text)} chars from {base_url}")
            return text
        except Exception as e:
            logger.error(f"API STT transcription failed: {e}")
            return None

    # ── Public interface ──

    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        settings = self._load_settings()
        if settings.get("stt_enabled") is False:
            return None
        provider = settings["stt_provider"]
        model = settings["stt_model"]
        language = settings.get("stt_language", "")

        if provider in ("disabled", "browser"):
            return None

        if provider == "local":
            return self._transcribe_local(audio_bytes, language)
        elif provider == "local-moonshine":
            return self._transcribe_moonshine(audio_bytes, language)
        elif provider == "local-moonshine-coreml":
            return self._transcribe_moonshine_coreml(audio_bytes, language)
        elif provider == "local-moonshine-coreml-streaming":
            return self._transcribe_moonshine_coreml_streaming(audio_bytes, language)
        elif provider.startswith("endpoint:"):
            endpoint_id = provider.split(":", 1)[1]
            return self._transcribe_api(audio_bytes, endpoint_id, model, language)
        else:
            logger.error(f"Unknown STT provider: {provider}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        settings = self._load_settings()
        provider = settings["stt_provider"]
        stt_enabled = settings.get("stt_enabled", False)
        # If toggle is off, report as disabled
        effective_provider = provider if stt_enabled else "disabled"

        stats = {
            "available": self.available and stt_enabled,
            "provider": effective_provider,
            "model": settings["stt_model"],
            "language": settings.get("stt_language", ""),
        }

        if provider == "local":
            whisper = self._get_whisper()
            stats["model_loaded"] = whisper is not None
        elif provider == "local-moonshine":
            moonshine = self._get_moonshine()
            stats["model_loaded"] = moonshine is not None
            stats["backend"] = "ONNX CPU (4-thread tuned)"
        elif provider == "local-moonshine-coreml":
            moonshine_coreml = self._get_moonshine_coreml()
            stats["model_loaded"] = moonshine_coreml is not None
            stats["backend"] = "CoreML ANE"
        elif provider == "local-moonshine-coreml-streaming":
            s_enc = self._get_moonshine_coreml_streaming()
            stats["model_loaded"] = s_enc is not None
            stats["backend"] = "CoreML ANE+CPU (streaming)"
        elif provider == "browser":
            stats["model"] = "Browser (Web Speech API)"
        elif provider.startswith("endpoint:"):
            stats["endpoint_id"] = provider.split(":", 1)[1]

        return stats


# Module-level singleton
_stt_service = None

def get_stt_service() -> STTService:
    global _stt_service
    if _stt_service is None:
        _stt_service = STTService()
    return _stt_service
