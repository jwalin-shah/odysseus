package cookbookserve

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"sync"
	"testing"
)

// ---------------------------------------------------------------------------
// Pure helpers.
// ---------------------------------------------------------------------------

func TestBuildKillCommand(t *testing.T) {
	tests := []struct {
		name       string
		sessionID  string
		remoteHost string
		sshPort    string
		want       string
	}{
		{
			name:      "local plain",
			sessionID: "serve-abc",
			want:      "tmux kill-session -t 'serve-abc'",
		},
		{
			name:      "local session with single quote",
			sessionID: "serve-it's-a-name",
			want:      `tmux kill-session -t 'serve-it'"'"'s-a-name'`,
		},
		{
			name:       "remote default ssh port",
			sessionID:  "serve-1",
			remoteHost: "user@box",
			sshPort:    "22",
			want:       "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no 'user@box' 'tmux kill-session -t 'serve-1''",
		},
		{
			name:       "remote custom ssh port",
			sessionID:  "serve-2",
			remoteHost: "host.local",
			sshPort:    "2222",
			want:       "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p '2222' 'host.local' 'tmux kill-session -t 'serve-2''",
		},
		{
			name:       "remote no port",
			sessionID:  "serve-3",
			remoteHost: "alice@gpu",
			sshPort:    "",
			want:       "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no 'alice@gpu' 'tmux kill-session -t 'serve-3''",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := BuildKillCommand(tc.sessionID, tc.remoteHost, tc.sshPort)
			if got != tc.want {
				t.Errorf("BuildKillCommand:\n got %q\nwant %q", got, tc.want)
			}
		})
	}
}

func TestExtractPortFromCommand(t *testing.T) {
	tests := []struct {
		name        string
		cmd         string
		defaultPort int
		want        int
	}{
		{"explicit --port wins", "vllm serve --port 9001 --model foo", 8080, 9001},
		{"OLLAMA_HOST env hint", "OLLAMA_HOST=0.0.0.0:11500 ollama serve", 8080, 11500},
		{"ollama fallback to 11434", "ollama run mistral", 8080, 11434},
		{"plain default 8080", "vllm serve --model foo", 8080, 8080},
		{"caller default honoured when no signal", "python -m thing", 1234, 1234},
		{"port precedes ollama keyword", "ollama --port 12000", 8080, 12000},
		{"OLLAMA_HOST precedes ollama keyword", "OLLAMA_HOST=h:13000 ollama serve", 8080, 13000},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := ExtractPortFromCommand(tc.cmd, tc.defaultPort)
			if got != tc.want {
				t.Errorf("ExtractPortFromCommand(%q,%d)=%d want %d", tc.cmd, tc.defaultPort, got, tc.want)
			}
		})
	}
}

func TestBuildBaseURL(t *testing.T) {
	tests := []struct {
		name string
		host string
		port int
		want string
	}{
		{"explicit host", "10.0.0.4", 9001, "http://10.0.0.4:9001/v1"},
		{"empty host falls back", "", 8080, "http://host.docker.internal:8080/v1"},
		{"localhost port 11434", "localhost", 11434, "http://localhost:11434/v1"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := BuildBaseURL(tc.host, tc.port)
			if got != tc.want {
				t.Errorf("BuildBaseURL(%q,%d)=%q want %q", tc.host, tc.port, got, tc.want)
			}
		})
	}
}

func TestStopSucceededFromExec(t *testing.T) {
	ec := func(n int) *int { v := n; return &v }
	tests := []struct {
		name string
		res  ExecResult
		want bool
	}{
		{"nil exit code", ExecResult{}, true},
		{"exit 0", ExecResult{ExitCode: ec(0)}, true},
		{"exit 1 'no server'", ExecResult{ExitCode: ec(1), Stderr: "no server running on /tmp/tmux"}, true},
		{"exit 1 can't find session", ExecResult{ExitCode: ec(1), Stderr: "can't find session: serve-x"}, true},
		{"exit 2 session not found", ExecResult{ExitCode: ec(2), Stderr: "session not found"}, true},
		{"exit 1 unrelated stderr", ExecResult{ExitCode: ec(1), Stderr: "permission denied"}, false},
		{"exit 137 silent", ExecResult{ExitCode: ec(137)}, false},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := StopSucceededFromExec(tc.res)
			if got != tc.want {
				t.Errorf("StopSucceededFromExec(%+v)=%v want %v", tc.res, got, tc.want)
			}
		})
	}
}

func TestHostFromRemote(t *testing.T) {
	tests := map[string]string{
		"":             "host.docker.internal",
		"box":          "box",
		"user@box":     "box",
		"a@b@c":        "c",
		"alice@10.1.2": "10.1.2",
	}
	for in, want := range tests {
		if got := HostFromRemote(in); got != want {
			t.Errorf("HostFromRemote(%q)=%q want %q", in, got, want)
		}
	}
}

func TestTask_SessionIDOrID(t *testing.T) {
	tests := []struct {
		name string
		t    Task
		want string
	}{
		{"prefers SessionID", Task{ID: "id", SessionID: "sid"}, "sid"},
		{"falls back to ID", Task{ID: "id"}, "id"},
		{"both empty", Task{}, ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.t.SessionIDOrID(); got != tc.want {
				t.Errorf("SessionIDOrID()=%q want %q", got, tc.want)
			}
		})
	}
}

func TestTask_IsTerminalStatus(t *testing.T) {
	tests := []struct {
		status string
		want   bool
	}{
		{"", false},
		{"stopped", true},
		{"Stopped", true},
		{"STOPPED", true},
		{"ended", true},
		{"killed", true},
		{"KILLED", true},
		{"crashed", true},
		{"CrAsHeD", true},
		{"running", false},
		{"starting", false},
		{"queued", false},
	}
	for _, tc := range tests {
		got := Task{Status: tc.status}.IsTerminalStatus()
		if got != tc.want {
			t.Errorf("IsTerminalStatus(%q)=%v want %v", tc.status, got, tc.want)
		}
	}
}

// ---------------------------------------------------------------------------
// FindTasksToStop.
// ---------------------------------------------------------------------------

func TestFindTasksToStop(t *testing.T) {
	ms := func(v int64) *int64 { return &v }
	state := &State{Tasks: []*Task{
		{ID: "future", SessionID: "fs", ScheduledStopAtMs: ms(2000)},
		{ID: "no-stamp", SessionID: "ns"},
		{ID: "already-stopped", SessionID: "as", Status: "Stopped", ScheduledStopAtMs: ms(100)},
		{ID: "killed", SessionID: "ks", Status: "killed", ScheduledStopAtMs: ms(100)},
		{ID: "crashed", SessionID: "cs", Status: "CRASHED", ScheduledStopAtMs: ms(100)},
		{ID: "valid-past", SessionID: "vs", ScheduledStopAtMs: ms(100)},
		{ID: "valid-no-sessionid", ScheduledStopAtMs: ms(100), Status: "running"},
		nil,
	}}
	got := FindTasksToStop(state, 1000)
	gotIDs := []string{}
	for _, t := range got {
		gotIDs = append(gotIDs, t.ID)
	}
	wantIDs := []string{"valid-past", "valid-no-sessionid"}
	if !reflect.DeepEqual(gotIDs, wantIDs) {
		t.Errorf("FindTasksToStop ids = %v want %v", gotIDs, wantIDs)
	}
}

func TestFindTasksToStop_nilState(t *testing.T) {
	if got := FindTasksToStop(nil, 1); got != nil {
		t.Errorf("FindTasksToStop(nil)=%v want nil", got)
	}
}

// ---------------------------------------------------------------------------
// Fake Client + StopTask flow.
// ---------------------------------------------------------------------------

type fakeClient struct {
	mu sync.Mutex

	endpoints   []Endpoint
	execResults []ExecResult
	execErr     error
	listErr     error
	deleteErr   error

	execCalls   []string
	deleteCalls []string
	listCalls   int
}

func (f *fakeClient) ListEndpoints(_ context.Context) ([]Endpoint, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.listCalls++
	if f.listErr != nil {
		return nil, f.listErr
	}
	out := make([]Endpoint, len(f.endpoints))
	copy(out, f.endpoints)
	return out, nil
}

func (f *fakeClient) DeleteEndpoint(_ context.Context, id string) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.deleteCalls = append(f.deleteCalls, id)
	return f.deleteErr
}

func (f *fakeClient) ExecCommand(_ context.Context, cmd string) (ExecResult, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.execCalls = append(f.execCalls, cmd)
	if f.execErr != nil {
		return ExecResult{}, f.execErr
	}
	if len(f.execResults) == 0 {
		zero := 0
		return ExecResult{ExitCode: &zero}, nil
	}
	res := f.execResults[0]
	if len(f.execResults) > 1 {
		f.execResults = f.execResults[1:]
	}
	return res, nil
}

func TestStopTask_successServeDeletesEndpoint(t *testing.T) {
	zero := 0
	http := &fakeClient{
		endpoints: []Endpoint{
			{ID: "ep-1", BaseURL: "http://host.docker.internal:9001/v1"},
			{ID: "ep-2", BaseURL: "http://other:1234/v1"},
		},
		execResults: []ExecResult{{ExitCode: &zero}},
	}
	lc := NewLifecycle()
	lc.Client = http
	task := Task{
		ID:        "task-x",
		SessionID: "serve-abc",
		Type:      "serve",
		Payload:   map[string]any{"_cmd": "vllm serve --port 9001 --model foo"},
	}
	if err := lc.StopTask(context.Background(), task); err != nil {
		t.Fatalf("StopTask: %v", err)
	}
	if len(http.execCalls) != 1 {
		t.Fatalf("execCalls=%d want 1", len(http.execCalls))
	}
	if want := "tmux kill-session -t 'serve-abc'"; http.execCalls[0] != want {
		t.Errorf("exec cmd=%q want %q", http.execCalls[0], want)
	}
	if len(http.deleteCalls) != 1 || http.deleteCalls[0] != "ep-1" {
		t.Errorf("deleteCalls=%v want [ep-1]", http.deleteCalls)
	}
	if http.listCalls != 1 {
		t.Errorf("listCalls=%d want 1", http.listCalls)
	}
}

func TestStopTask_nonServeSkipsEndpointDelete(t *testing.T) {
	http := &fakeClient{}
	lc := NewLifecycle()
	lc.Client = http
	task := Task{SessionID: "sess-1", Type: "exec",
		Payload: map[string]any{"_cmd": "python foo.py"}}
	if err := lc.StopTask(context.Background(), task); err != nil {
		t.Fatalf("StopTask: %v", err)
	}
	if http.listCalls != 0 {
		t.Errorf("non-serve task should not list endpoints: %d", http.listCalls)
	}
	if len(http.deleteCalls) != 0 {
		t.Errorf("non-serve task should not delete endpoints: %v", http.deleteCalls)
	}
}

func TestStopTask_hostPortFallbackMatch(t *testing.T) {
	zero := 0
	http := &fakeClient{
		endpoints: []Endpoint{
			{ID: "ep-host", BaseURL: "http://0.0.0.0:11434/api"},
		},
		execResults: []ExecResult{{ExitCode: &zero}},
	}
	lc := NewLifecycle()
	lc.Client = http
	task := Task{
		SessionID:  "s",
		Type:       "serve",
		RemoteHost: "user@0.0.0.0",
		Payload:    map[string]any{"_cmd": "ollama serve"},
	}
	if err := lc.StopTask(context.Background(), task); err != nil {
		t.Fatalf("StopTask: %v", err)
	}
	if len(http.deleteCalls) != 1 || http.deleteCalls[0] != "ep-host" {
		t.Errorf("expected fallback host:port match to find ep-host, got %v", http.deleteCalls)
	}
}

func TestStopTask_emptySessionID(t *testing.T) {
	lc := NewLifecycle()
	lc.Client = &fakeClient{}
	err := lc.StopTask(context.Background(), Task{})
	if !errors.Is(err, ErrMissingSessionID) {
		t.Fatalf("expected ErrMissingSessionID, got %v", err)
	}
}

func TestStopTask_killFailureSurfaced(t *testing.T) {
	bad := 137
	http := &fakeClient{execResults: []ExecResult{{ExitCode: &bad, Stderr: "permission denied"}}}
	lc := NewLifecycle()
	lc.Client = http
	err := lc.StopTask(context.Background(), Task{SessionID: "s"})
	if !errors.Is(err, ErrKillFailed) {
		t.Fatalf("expected ErrKillFailed, got %v", err)
	}
}

func TestStopTask_killExecErrorBubbles(t *testing.T) {
	http := &fakeClient{execErr: errors.New("network down")}
	lc := NewLifecycle()
	lc.Client = http
	err := lc.StopTask(context.Background(), Task{SessionID: "s"})
	if err == nil || err.Error() != "network down" {
		t.Fatalf("expected wrapped network-down error, got %v", err)
	}
}

func TestStopTask_endpointDeleteFailureDoesNotBlockStop(t *testing.T) {
	zero := 0
	http := &fakeClient{
		endpoints:   []Endpoint{{ID: "ep-1", BaseURL: "http://host.docker.internal:9001/v1"}},
		execResults: []ExecResult{{ExitCode: &zero}},
		deleteErr:   errors.New("server says no"),
	}
	lc := NewLifecycle()
	lc.Client = http
	task := Task{
		SessionID: "s",
		Type:      "serve",
		Payload:   map[string]any{"_cmd": "vllm serve --port 9001"},
	}
	if err := lc.StopTask(context.Background(), task); err != nil {
		t.Fatalf("StopTask should not fail when endpoint delete fails: %v", err)
	}
}

func TestStopTask_nilClient(t *testing.T) {
	lc := NewLifecycle()
	err := lc.StopTask(context.Background(), Task{SessionID: "s"})
	if !errors.Is(err, ErrNilClient) {
		t.Fatalf("expected ErrNilClient, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// State-file round trip + Tick integration.
// ---------------------------------------------------------------------------

func TestStateFileRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "state.json")
	stop := int64(1700000000000)
	flip := int64(1700000005000)
	orig := &State{
		Tasks: []*Task{
			{
				ID:                 "task-a",
				SessionID:          "serve-a",
				RemoteHost:         "user@gpu1",
				SSHPort:            "2222",
				Type:               "serve",
				Status:             "running",
				ScheduledStopAtMs:  &stop,
				LastStatusFlipAtMs: &flip,
				Payload:            map[string]any{"_cmd": "vllm serve --port 9001"},
			},
		},
		Extra: map[string]json.RawMessage{
			"_meta": json.RawMessage(`{"writer":"ui"}`),
		},
	}
	if err := WriteStateFileAtomic(path, orig); err != nil {
		t.Fatalf("write: %v", err)
	}
	got, err := ReadStateFile(path)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	if len(got.Tasks) != 1 {
		t.Fatalf("tasks=%d want 1", len(got.Tasks))
	}
	gt := got.Tasks[0]
	if gt.ID != "task-a" || gt.SessionID != "serve-a" || gt.Type != "serve" {
		t.Errorf("task identity mismatch: %+v", gt)
	}
	if gt.ScheduledStopAtMs == nil || *gt.ScheduledStopAtMs != stop {
		t.Errorf("stop ms not preserved: %+v", gt.ScheduledStopAtMs)
	}
	if got.Extra["_meta"] == nil {
		t.Errorf("Extra _meta not preserved: %v", got.Extra)
	}
}

func TestReadStateFile_missing(t *testing.T) {
	dir := t.TempDir()
	_, err := ReadStateFile(filepath.Join(dir, "no-such-file.json"))
	if !os.IsNotExist(err) {
		t.Fatalf("expected os.IsNotExist, got %v", err)
	}
}

func TestReadStateFile_empty(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "empty.json")
	if err := os.WriteFile(p, []byte(""), 0o644); err != nil {
		t.Fatal(err)
	}
	s, err := ReadStateFile(p)
	if err != nil {
		t.Fatalf("read empty: %v", err)
	}
	if s == nil || len(s.Tasks) != 0 {
		t.Errorf("empty state should have no tasks: %+v", s)
	}
}

func TestReadStateFile_emptyPath(t *testing.T) {
	_, err := ReadStateFile("")
	if !errors.Is(err, ErrEmptyStatePath) {
		t.Fatalf("expected ErrEmptyStatePath, got %v", err)
	}
}

func TestWriteStateFileAtomic_emptyPath(t *testing.T) {
	err := WriteStateFileAtomic("", &State{})
	if !errors.Is(err, ErrEmptyStatePath) {
		t.Fatalf("expected ErrEmptyStatePath, got %v", err)
	}
}

func TestTick_stopsExpiredTasksAndPatchesState(t *testing.T) {
	zero := 0
	dir := t.TempDir()
	statePath := filepath.Join(dir, "state.json")
	stopPast := int64(500)
	stopFuture := int64(5_000_000)
	orig := &State{Tasks: []*Task{
		{ID: "a", SessionID: "serve-a", Type: "serve",
			ScheduledStopAtMs: &stopPast, Status: "running",
			Payload: map[string]any{"_cmd": "vllm serve --port 9001"}},
		{ID: "b", SessionID: "serve-b", Type: "exec",
			ScheduledStopAtMs: &stopFuture, Status: "running"},
		{ID: "c", SessionID: "serve-c", Type: "serve",
			ScheduledStopAtMs: &stopPast, Status: "stopped"},
	}, Extra: map[string]json.RawMessage{}}
	if err := WriteStateFileAtomic(statePath, orig); err != nil {
		t.Fatal(err)
	}
	http := &fakeClient{
		endpoints:   []Endpoint{{ID: "ep-1", BaseURL: "http://host.docker.internal:9001/v1"}},
		execResults: []ExecResult{{ExitCode: &zero}},
	}
	lc := NewLifecycle()
	lc.Client = http
	lc.StateFilePath = statePath
	lc.NowMs = func() int64 { return 1000 }
	if err := lc.Tick(context.Background()); err != nil {
		t.Fatalf("Tick: %v", err)
	}
	if len(http.execCalls) != 1 {
		t.Fatalf("execCalls=%d want 1 (only task 'a' is past+running+sid)", len(http.execCalls))
	}
	if len(http.deleteCalls) != 1 || http.deleteCalls[0] != "ep-1" {
		t.Errorf("deleteCalls=%v want [ep-1]", http.deleteCalls)
	}
	got, err := ReadStateFile(statePath)
	if err != nil {
		t.Fatalf("re-read: %v", err)
	}
	if len(got.Tasks) != 3 {
		t.Fatalf("task count changed: %d", len(got.Tasks))
	}
	byID := map[string]*Task{}
	for _, tk := range got.Tasks {
		byID[tk.ID] = tk
	}
	if byID["a"].Status != "stopped" {
		t.Errorf("task a status=%q want stopped", byID["a"].Status)
	}
	if byID["a"].ScheduledStopAtMs != nil {
		t.Errorf("task a ScheduledStopAtMs should be cleared: %v", byID["a"].ScheduledStopAtMs)
	}
	if byID["a"].LastStatusFlipAtMs == nil || *byID["a"].LastStatusFlipAtMs != 1000 {
		t.Errorf("task a LastStatusFlipAtMs=%v want *1000", byID["a"].LastStatusFlipAtMs)
	}
	if byID["b"].Status != "running" {
		t.Errorf("task b should be untouched: %+v", byID["b"])
	}
}

func TestTick_missingStateFile_isNoop(t *testing.T) {
	dir := t.TempDir()
	http := &fakeClient{}
	lc := NewLifecycle()
	lc.Client = http
	lc.StateFilePath = filepath.Join(dir, "missing.json")
	if err := lc.Tick(context.Background()); err != nil {
		t.Fatalf("expected no error for missing state file, got %v", err)
	}
	if len(http.execCalls)+http.listCalls+len(http.deleteCalls) != 0 {
		t.Errorf("expected zero HTTP calls, got exec=%d list=%d delete=%d",
			len(http.execCalls), http.listCalls, len(http.deleteCalls))
	}
}

func TestTick_killFailureLeavesTaskAlone(t *testing.T) {
	bad := 1
	dir := t.TempDir()
	statePath := filepath.Join(dir, "state.json")
	stopPast := int64(500)
	orig := &State{Tasks: []*Task{
		{ID: "a", SessionID: "serve-a", Type: "exec",
			ScheduledStopAtMs: &stopPast, Status: "running"},
	}}
	if err := WriteStateFileAtomic(statePath, orig); err != nil {
		t.Fatal(err)
	}
	http := &fakeClient{execResults: []ExecResult{{ExitCode: &bad, Stderr: "no idea what happened"}}}
	lc := NewLifecycle()
	lc.Client = http
	lc.StateFilePath = statePath
	lc.NowMs = func() int64 { return 1000 }
	if err := lc.Tick(context.Background()); err != nil {
		t.Fatalf("Tick: %v", err)
	}
	got, err := ReadStateFile(statePath)
	if err != nil {
		t.Fatal(err)
	}
	if got.Tasks[0].Status != "running" {
		t.Errorf("task should still be running after failed stop: %q", got.Tasks[0].Status)
	}
	if got.Tasks[0].ScheduledStopAtMs == nil {
		t.Errorf("ScheduledStopAtMs should be preserved after failed stop")
	}
}

func TestTick_nilClientErrors(t *testing.T) {
	lc := NewLifecycle()
	lc.StateFilePath = "/tmp/whatever"
	err := lc.Tick(context.Background())
	if !errors.Is(err, ErrNilClient) {
		t.Fatalf("expected ErrNilClient, got %v", err)
	}
}

// Sanity check that the package-level token defaults to "dev" and respects
// the env var override at call time (matching the Python late binding).
func TestToken_defaults(t *testing.T) {
	t.Setenv(TokenEnv, "")
	if got := Token(); got != "dev" {
		t.Errorf("default token=%q want dev", got)
	}
	t.Setenv(TokenEnv, "real-token")
	if got := Token(); got != "real-token" {
		t.Errorf("override token=%q want real-token", got)
	}
}

func TestAPIBase_defaults(t *testing.T) {
	t.Setenv(APIBaseEnv, "")
	if got := APIBase(); got != DefaultAPIBase {
		t.Errorf("default APIBase=%q want %q", got, DefaultAPIBase)
	}
	t.Setenv(APIBaseEnv, "http://example.com/")
	if got := APIBase(); got != "http://example.com" {
		t.Errorf("APIBase should trim trailing slash, got %q", got)
	}
}
