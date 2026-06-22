import AppKit
import Foundation
import SwiftUI
import UserNotifications
import FleetCore

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var popover: NSPopover!
    private var stateReader: StateReader!
    private var fleetListVC: NSHostingController<FleetListView>!
    private var currentTasks: [Task] = []
    private var eventMonitor: Any?
    private var notifications: NotificationDelegateBox!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        // Status bar item
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "person.3.fill", accessibilityDescription: "Fleet")
            button.imagePosition = .imageLeading
            button.title = "0"
            button.action = #selector(togglePopover(_:))
            button.target = self
        }

        // Popover hosting FleetListView
        popover = NSPopover()
        popover.behavior = .transient
        popover.contentSize = NSSize(width: 380, height: 460)
        let listView = FleetListView(tasks: currentTasks, onSelect: { [weak self] task in
            self?.focusTask(task)
            self?.popover.performClose(nil)
        })
        fleetListVC = NSHostingController(rootView: listView)
        popover.contentViewController = fleetListVC

        // State reader
        let home = FileManager.default.homeDirectoryForCurrentUser
        let stateDir = home.appendingPathComponent("projects/firstmate/state")
        stateReader = StateReader(stateDirectory: stateDir) { [weak self] tasks in
            self?.handleTasks(tasks)
        }
        stateReader.start()

        // Notifications
        let notifBox = NotificationDelegateBox()
        notifications = notifBox
        UNUserNotificationCenter.current().delegate = notifBox
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleStatusTransition(_:)),
            name: .fleetStatusTransitioned,
            object: nil
        )

        // Click outside popover closes it
        eventMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { [weak self] _ in
            if let popover = self?.popover, popover.isShown { popover.performClose(nil) }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let monitor = eventMonitor { NSEvent.removeMonitor(monitor) }
        stateReader?.stop()
    }

    @objc private func togglePopover(_ sender: AnyObject?) {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(sender)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }

    private func handleTasks(_ tasks: [Task]) {
        currentTasks = tasks
        let inflight = tasks.filter { $0.isInflight }.count
        if let button = statusItem.button {
            button.title = " \(inflight)"
            button.image = NSImage(systemSymbolName: inflight > 0 ? "person.3.fill" : "person.3", accessibilityDescription: "Fleet")
        }
        if let vc = fleetListVC {
            vc.rootView = FleetListView(tasks: tasks, onSelect: { [weak self] task in
                self?.focusTask(task)
                self?.popover.performClose(nil)
            })
        }
    }

    @objc private func handleStatusTransition(_ note: Notification) {
        guard let transitions = note.userInfo?["transitions"] as? [String: [String: String]] else { return }
        for (id, info) in transitions {
            guard let prefix = info["prefix"] else { continue }
            let task = currentTasks.first { $0.id == id }
            let body = task?.lastStatusBody ?? "Task \(id)"
            notify(prefix: prefix, taskID: id, body: body)
        }
    }

    private func notify(prefix: String, taskID: String, body: String) {
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

    private func focusTask(_ task: Task) {
        guard !task.window.isEmpty else { return }
        // Run tmux select-window
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/tmux")
        p.arguments = ["select-window", "-t", task.window]
        try? p.run()
        p.waitUntilExit()
        // Bring Ghostty (or any terminal) forward
        let terminalNames = ["Ghostty", "iTerm2", "Terminal", "WezTerm", "Alacritty"]
        for app in NSWorkspace.shared.runningApplications {
            if let name = app.localizedName, terminalNames.contains(name) {
                app.activate(options: .activateIgnoringOtherApps)
                break
            }
        }
    }
}

/// NSObject wrapper for UNUserNotificationCenterDelegate so we can avoid
/// main-actor-isolated protocol conformance.
final class NotificationDelegateBox: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
}
