// Tick + StopTask + endpoint-deletion logic. Pure of the loop body itself
// (which lives in lifecycle.go's Run) so tests can drive a single iteration
// without spinning up the forever loop.

package cookbookserve

import (
	"context"
	"os"
	"strings"
)

// FindTasksToStop returns the tasks that should be stopped on this tick:
//   - ScheduledStopAtMs is set and <= nowMs
//   - status is not already terminal
//   - sessionId or id is non-empty
func FindTasksToStop(s *State, nowMs int64) []Task {
	if s == nil {
		return nil
	}
	out := make([]Task, 0, len(s.Tasks))
	for _, t := range s.Tasks {
		if t == nil || t.ScheduledStopAtMs == nil {
			continue
		}
		if *t.ScheduledStopAtMs > nowMs {
			continue
		}
		if t.IsTerminalStatus() {
			continue
		}
		if t.SessionIDOrID() == "" {
			continue
		}
		out = append(out, *t)
	}
	return out
}

// Tick executes a single iteration of the lifecycle loop: read the state
// file, find expired tasks, kill each one's tmux session, drop the
// auto-registered endpoint for "serve" tasks, then re-read the state file
// and patch only the successfully-stopped entries before writing atomically.
//
// Errors from a single task are logged and the loop continues with the next
// task; an error return means the whole tick failed before any work was
// done (state file unreadable, etc.). A missing state file is a no-op
// rather than an error.
func (l *Lifecycle) Tick(ctx context.Context) error {
	if l == nil {
		return ErrNilLifecycle
	}
	if l.Client == nil {
		return ErrNilClient
	}
	state, err := ReadStateFile(l.StateFilePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		l.logger().Printf("cookbook_serve_lifecycle: state file unreadable (%v), skipping tick", err)
		return nil
	}
	now := l.nowMs()
	toStop := FindTasksToStop(state, now)
	if len(toStop) == 0 {
		return nil
	}
	stoppedSIDs := map[string]struct{}{}
	for _, t := range toStop {
		sid := t.SessionIDOrID()
		host := preferHost(t)
		if err := l.StopTask(ctx, t); err != nil {
			l.logger().Printf("cookbook_serve_lifecycle: stop %s (host=%s): failed: %v",
				sid, host, err)
			continue
		}
		l.logger().Printf("cookbook_serve_lifecycle: stop %s (host=%s): ok", sid, host)
		stoppedSIDs[sid] = struct{}{}
	}
	if len(stoppedSIDs) == 0 {
		return nil
	}
	// Re-read the state file so concurrent UI writes (task adds, status
	// flips, config edits) are not silently overwritten. Apply only our
	// stop mutations to the fresh snapshot.
	fresh, err := ReadStateFile(l.StateFilePath)
	if err != nil {
		l.logger().Printf("cookbook_serve_lifecycle: state re-read failed (%v), patching original", err)
		fresh = state
	}
	patchStoppedTasks(fresh, stoppedSIDs, now)
	if err := WriteStateFileAtomic(l.StateFilePath, fresh); err != nil {
		l.logger().Printf("cookbook_serve_lifecycle: state write failed: %v", err)
		return err
	}
	return nil
}

// StopTask kills the tmux session for task and (for Type=="serve" tasks)
// drops the auto-registered endpoint. Returns nil on a successful kill; the
// endpoint delete is best-effort and never blocks success of the stop.
func (l *Lifecycle) StopTask(ctx context.Context, task Task) error {
	if l == nil {
		return ErrNilLifecycle
	}
	if l.Client == nil {
		return ErrNilClient
	}
	sid := task.SessionIDOrID()
	if sid == "" {
		return ErrMissingSessionID
	}
	cmd := BuildKillCommand(sid, task.RemoteHost, task.SSHPort)
	res, err := l.Client.ExecCommand(ctx, cmd)
	if err != nil {
		return err
	}
	if !StopSucceededFromExec(res) {
		return ErrKillFailed
	}
	if strings.EqualFold(task.Type, "serve") {
		if derr := l.deleteEndpointForTask(ctx, task); derr != nil {
			l.logger().Printf("cookbook_serve_lifecycle: endpoint delete failed: %v", derr)
		}
	}
	return nil
}

// deleteEndpointForTask is the Go equivalent of _delete_endpoint_for_task.
// Errors are returned to the caller rather than swallowed so StopTask can
// log them, but they never fail the stop itself.
func (l *Lifecycle) deleteEndpointForTask(ctx context.Context, task Task) error {
	payload := task.Payload
	if payload == nil {
		return nil
	}
	cmdAny, ok := payload["_cmd"]
	if !ok {
		return nil
	}
	cmd, _ := cmdAny.(string)
	port := ExtractPortFromCommand(cmd, 8080)
	host := HostFromRemote(task.RemoteHost)
	baseURL := BuildBaseURL(host, port)
	eps, err := l.Client.ListEndpoints(ctx)
	if err != nil {
		return err
	}
	var target *Endpoint
	for i := range eps {
		if eps[i].BaseURL == baseURL {
			target = &eps[i]
			break
		}
	}
	if target == nil {
		// Fall back to host:port substring match for the 0.0.0.0 case.
		needle := stripScheme(baseURL)
		needle = stripV1(needle)
		for i := range eps {
			if strings.Contains(eps[i].BaseURL, needle) {
				target = &eps[i]
				break
			}
		}
	}
	if target == nil || target.ID == "" {
		return nil
	}
	if err := l.Client.DeleteEndpoint(ctx, target.ID); err != nil {
		return err
	}
	l.logger().Printf("cookbook_serve_lifecycle: deleted endpoint %s (%s) after scheduled stop",
		target.ID, target.BaseURL)
	return nil
}

// patchStoppedTasks marks every task in s whose sessionId/id is in
// stoppedSIDs as status="stopped" and clears ScheduledStopAtMs. Tasks not
// in the set are left untouched.
func patchStoppedTasks(s *State, stoppedSIDs map[string]struct{}, nowMs int64) {
	if s == nil {
		return
	}
	for _, t := range s.Tasks {
		if t == nil {
			continue
		}
		sid := t.SessionIDOrID()
		if _, ok := stoppedSIDs[sid]; !ok {
			continue
		}
		t.Status = "stopped"
		t.ScheduledStopAtMs = nil
		flip := nowMs
		t.LastStatusFlipAtMs = &flip
	}
}

func preferHost(t Task) string {
	if t.RemoteHost != "" {
		return t.RemoteHost
	}
	return "local"
}

// stripScheme drops "http://" / "https://" from a base URL.
func stripScheme(u string) string {
	if i := strings.Index(u, "://"); i >= 0 {
		return u[i+3:]
	}
	return u
}

// stripV1 drops a trailing "/v1" from a host:port[/v1] string so substring
// matches against arbitrary base URLs still hit.
func stripV1(s string) string {
	return strings.TrimSuffix(strings.TrimRight(s, "/"), "/v1")
}
