import Foundation

/// Scans `~/projects/firstmate/state/*.status` + matching `.meta` files and
/// emits a snapshot of `Task` values whenever the directory changes.
public final class StateReader {
    public let stateDirectory: URL
    public let onChange: ([Task]) -> Void

    private let queue = DispatchQueue(label: "firstmate.fleet.state-reader")
    private var directorySource: DispatchSourceFileSystemObject?
    private var directoryFD: CInt = -1
    private var fallbackTimer: DispatchSourceTimer?
    private var fileSources: [String: DispatchSourceFileSystemObject] = [:]
    private var fileFDs: [String: CInt] = [:]
    private var lastTasks: [Task] = []
    private var lastPrefixes: [String: String] = [:]
    private var hasStarted = false

    public init(stateDirectory: URL, onChange: @escaping ([Task]) -> Void) {
        self.stateDirectory = stateDirectory
        self.onChange = onChange
    }

    deinit { stop() }

    public func start() {
        queue.async { [weak self] in
            self?.installWatchers()
        }
    }

    public func stop() {
        queue.async { [weak self] in
            self?.removeWatchers()
        }
    }

    public func read() -> [Task] {
        return queue.sync { lastTasks }
    }

    public func prefixes() -> [String: String] {
        return queue.sync { lastPrefixes }
    }

    // MARK: - Internals

    private func installWatchers() {
        // Initial scan
        emitChange(scanOnce())

        // Open directory FD for rename/delete/write events
        let fd = open(stateDirectory.path, O_EVTONLY)
        if fd >= 0 {
            directoryFD = fd
            let source = DispatchSource.makeFileSystemObjectSource(
                fileDescriptor: fd,
                eventMask: [.write, .extend, .rename, .delete],
                queue: queue
            )
            source.setEventHandler { [weak self] in
                self?.refreshFileWatchers()
                self?.emitChange(self?.scanOnce() ?? [])
            }
            source.setCancelHandler { [weak self] in
                if let f = self?.directoryFD, f >= 0 { close(f) }
                self?.directoryFD = -1
            }
            source.resume()
            directorySource = source
        }

        // Fallback timer — every 3 seconds
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now() + 3, repeating: 3)
        timer.setEventHandler { [weak self] in
            guard let self = self else { return }
            self.emitChange(self.scanOnce())
        }
        timer.resume()
        fallbackTimer = timer

        hasStarted = true
        refreshFileWatchers()
    }

    private func removeWatchers() {
        directorySource?.cancel()
        directorySource = nil
        for (_, src) in fileSources { src.cancel() }
        fileSources.removeAll()
        for (_, fd) in fileFDs { if fd >= 0 { close(fd) } }
        fileFDs.removeAll()
        fallbackTimer?.cancel()
        fallbackTimer = nil
    }

    private func refreshFileWatchers() {
        let fm = FileManager.default
        let entries: [String]
        do {
            entries = try fm.contentsOfDirectory(atPath: stateDirectory.path)
        } catch {
            return
        }
        var statusIDs = Set<String>()
        for entry in entries where entry.hasSuffix(".status") {
            let id = String(entry.dropLast(".status".count))
            statusIDs.insert(id)
        }

        // Remove watchers for files that no longer exist
        for (id, src) in fileSources where !statusIDs.contains(id) {
            src.cancel()
            fileSources.removeValue(forKey: id)
            if let fd = fileFDs.removeValue(forKey: id), fd >= 0 { close(fd) }
        }

        // Add watchers for new files
        for id in statusIDs where fileSources[id] == nil {
            let path = stateDirectory.appendingPathComponent("\(id).status").path
            let fd = open(path, O_EVTONLY)
            if fd < 0 { continue }
            fileFDs[id] = fd
            let source = DispatchSource.makeFileSystemObjectSource(
                fileDescriptor: fd,
                eventMask: [.write, .extend, .delete, .rename],
                queue: queue
            )
            source.setEventHandler { [weak self] in
                self?.emitChange(self?.scanOnce() ?? [])
            }
            source.setCancelHandler { [weak self] in
                if let f = self?.fileFDs.removeValue(forKey: id), f >= 0 { close(f) }
            }
            source.resume()
            fileSources[id] = source
        }
    }

    private func scanOnce() -> [Task] {
        let fm = FileManager.default
        let entries: [String]
        do {
            entries = try fm.contentsOfDirectory(atPath: stateDirectory.path)
        } catch {
            return []
        }
        var tasks: [Task] = []
        var prefixes: [String: String] = [:]
        for entry in entries where entry.hasSuffix(".status") {
            let id = String(entry.dropLast(".status".count))
            // Skip dotfiles / hidden helpers (e.g. ".watch.lock", ".count-...")
            if id.hasPrefix(".") { continue }
            let statusURL = stateDirectory.appendingPathComponent("\(id).status")
            let metaURL = stateDirectory.appendingPathComponent("\(id).meta")
            guard let raw = try? String(contentsOf: statusURL, encoding: .utf8) else { continue }
            let lastLine = raw.split(whereSeparator: \.isNewline).last.map(String.init) ?? ""
            let mtime = (try? fm.attributesOfItem(atPath: statusURL.path)[.modificationDate] as? Date) ?? Date.distantPast
            let (prefix, body) = parseStatusLine(lastLine)
            let meta = parseMeta(metaURL)
            prefixes[id] = prefix
            tasks.append(Task(
                id: id,
                repo: meta["repo"] ?? "?",
                kind: meta["kind"] ?? "?",
                harness: meta["harness"] ?? "?",
                window: meta["window"] ?? "",
                rawStatus: raw,
                lastStatusLine: lastLine,
                lastStatusPrefix: prefix,
                lastStatusBody: body,
                mtime: mtime
            ))
        }
        tasks.sort { $0.mtime > $1.mtime }
        lastTasks = tasks
        lastPrefixes = prefixes
        return tasks
    }

    private func emitChange(_ tasks: [Task]) {
        let onChange = self.onChange
        // Dedupe notification triggers by checking prefix deltas
        let previous = lastPrefixes
        var newPrefixes: [String: String] = [:]
        for task in tasks { newPrefixes[task.id] = task.lastStatusPrefix }
        let transitions = detectTransitions(prev: previous, next: newPrefixes)
        lastPrefixes = newPrefixes
        DispatchQueue.main.async {
            onChange(tasks)
            NotificationCenter.default.post(
                name: .fleetStatusTransitioned,
                object: nil,
                userInfo: ["transitions": transitions]
            )
        }
    }

    private func detectTransitions(prev: [String: String], next: [String: String]) -> [String: Any] {
        var transitions: [String: [String: String]] = [:]
        for (id, newPrefix) in next {
            let oldPrefix = prev[id] ?? ""
            if oldPrefix != newPrefix, newPrefix == "done" || newPrefix == "blocked" {
                transitions[id] = ["prefix": newPrefix]
            }
        }
        return ["transitions": transitions]
    }

    private func parseStatusLine(_ line: String) -> (prefix: String, body: String) {
        guard let colon = line.firstIndex(of: ":") else { return (line.trimmingCharacters(in: .whitespaces), "") }
        let prefix = String(line[..<colon]).trimmingCharacters(in: .whitespaces)
        let body = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
        return (prefix, body)
    }

    private func parseMeta(_ url: URL) -> [String: String] {
        guard let raw = try? String(contentsOf: url, encoding: .utf8) else { return [:] }
        var dict: [String: String] = [:]
        for line in raw.split(whereSeparator: \.isNewline) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed.hasPrefix("#") { continue }
            guard let eq = trimmed.firstIndex(of: "=") else { continue }
            let key = String(trimmed[..<eq])
            let value = String(trimmed[trimmed.index(after: eq)...])
            dict[key] = value
        }
        return dict
    }
}

public extension Notification.Name {
    static let fleetStatusTransitioned = Notification.Name("FleetStatusTransitioned")
}
