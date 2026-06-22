import Foundation
import UserNotifications

/// Wraps UNUserNotificationCenter with a small fire-on-transition API.
public final class FleetNotifier {
    public static let shared = FleetNotifier()

    private var authorized: Bool = false

    public func start() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { [weak self] granted, _ in
            self?.authorized = granted
        }
    }

    public func fire(prefix: String, taskID: String, body: String) {
        guard prefix == "done" || prefix == "blocked" else { return }
        let content = UNMutableNotificationContent()
        content.title = prefix == "done" ? "Task done" : "Task blocked"
        content.body = "\(taskID): \(body)"
        content.sound = .default
        let req = UNNotificationRequest(
            identifier: "fleet.\(prefix).\(taskID).\(Int(Date().timeIntervalSince1970))",
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(req) { _ in }
    }
}
