import AppKit
import SwiftUI
import FleetCore

struct FleetListView: View {
    let tasks: [Task]
    let onSelect: (Task) -> Void

    var inflight: [Task] { tasks.filter { $0.isInflight } }
    var blocked: [Task] { tasks.filter { $0.isBlocked } }
    var queued: [Task] { tasks.filter { $0.isQueued } }
    var done: [Task] { tasks.filter { $0.isDone } }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    if !inflight.isEmpty {
                        sectionHeader("Inflight", count: inflight.count, color: .blue)
                        ForEach(inflight) { row($0) }
                    }
                    if !blocked.isEmpty {
                        sectionHeader("Blocked", count: blocked.count, color: .red)
                        ForEach(blocked) { row($0) }
                    }
                    if !queued.isEmpty {
                        sectionHeader("Queued", count: queued.count, color: .orange)
                        ForEach(queued) { row($0) }
                    }
                    if !done.isEmpty {
                        sectionHeader("Done (recent)", count: done.count, color: .green)
                        ForEach(done.prefix(5)) { row($0) }
                    }
                    if tasks.isEmpty {
                        Text("No tasks found")
                            .foregroundColor(.secondary)
                            .padding()
                    }
                }
                .padding(.vertical, 6)
            }
        }
        .frame(width: 360, height: 440)
    }

    private var header: some View {
        HStack {
            Image(systemName: "person.3.fill")
            Text("Fleet")
                .font(.headline)
            Spacer()
            Text("\(inflight.count) inflight")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    private func sectionHeader(_ title: String, count: Int, color: Color) -> some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(title)
                .font(.subheadline.weight(.semibold))
            Text("(\(count))")
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
    }

    private func row(_ task: Task) -> some View {
        Button(action: { onSelect(task) }) {
            HStack(alignment: .top, spacing: 8) {
                statusDot(for: task)
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(task.id)
                            .font(.system(.body, design: .monospaced).weight(.medium))
                            .lineLimit(1)
                        Spacer()
                        Text(task.harness)
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 1)
                            .background(Color.secondary.opacity(0.15), in: Capsule())
                    }
                    if !task.lastStatusBody.isEmpty {
                        Text(task.lastStatusBody)
                            .font(.caption)
                            .foregroundColor(.primary)
                            .lineLimit(2)
                    }
                    HStack(spacing: 6) {
                        Text(task.repo)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text("•")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text(task.kind)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        if !task.window.isEmpty {
                            Text("•")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                            Text(task.window)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func statusDot(for task: Task) -> some View {
        let color: Color
        if task.isInflight { color = .blue }
        else if task.isBlocked { color = .red }
        else if task.isDone { color = .green }
        else if task.isQueued { color = .orange }
        else { color = .gray }
        return Circle()
            .fill(color)
            .frame(width: 10, height: 10)
            .padding(.top, 4)
    }
}
