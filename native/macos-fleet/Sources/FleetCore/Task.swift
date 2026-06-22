import Foundation

/// Represents a firstmate task parsed from a `<id>.status` + `<id>.meta` pair.
public struct Task: Identifiable, Hashable, Codable {
    public let id: String
    public let repo: String
    public let kind: String
    public let harness: String
    public let window: String
    public let rawStatus: String
    public let lastStatusLine: String
    public let lastStatusPrefix: String
    public let lastStatusBody: String
    public let mtime: Date

    public var isInflight: Bool { lastStatusPrefix == "working" || lastStatusPrefix == "starting" }
    public var isBlocked: Bool { lastStatusPrefix == "blocked" }
    public var isDone: Bool { lastStatusPrefix == "done" }
    public var isQueued: Bool { lastStatusPrefix == "queued" }

    public init(
        id: String,
        repo: String,
        kind: String,
        harness: String,
        window: String,
        rawStatus: String,
        lastStatusLine: String,
        lastStatusPrefix: String,
        lastStatusBody: String,
        mtime: Date
    ) {
        self.id = id
        self.repo = repo
        self.kind = kind
        self.harness = harness
        self.window = window
        self.rawStatus = rawStatus
        self.lastStatusLine = lastStatusLine
        self.lastStatusPrefix = lastStatusPrefix
        self.lastStatusBody = lastStatusBody
        self.mtime = mtime
    }
}
