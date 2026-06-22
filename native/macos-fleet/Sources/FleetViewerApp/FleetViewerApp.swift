import AppKit
import Foundation
import SwiftUI
import UserNotifications
import FleetCore

@main
struct FleetViewerAppMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        // Hold a strong reference so the delegate isn't deallocated.
        let holder = DelegateHolder(delegate: delegate)
        objc_setAssociatedObject(app, &FleetViewerAppMain.assocKey, holder, .OBJC_ASSOCIATION_RETAIN)
        app.run()
    }

    private static var assocKey: UInt8 = 0
}

private final class DelegateHolder {
    let delegate: AppDelegate
    init(delegate: AppDelegate) { self.delegate = delegate }
}
