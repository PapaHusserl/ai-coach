// Запасной вариант Б: дамп событий календаря через EventKit с вшитым Info.plist.
// Только чтение. Сборка (Info.plist вшивается в секцию __TEXT,__info_plist):
//
//   cat > /tmp/Info.plist <<'PL'
//   <?xml version="1.0" encoding="UTF-8"?>
//   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
//   <plist version="1.0"><dict>
//     <key>CFBundleIdentifier</key><string>local.ai-coach.calendumpspike</string>
//     <key>NSCalendarsFullAccessUsageDescription</key><string>Чтение календаря для оценки загруженности</string>
//   </dict></plist>
//   PL
//   swiftc -O spikes/workload/swift/CalendarDump.swift -o spikes/out/CalendarDump \
//     -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker /tmp/Info.plist
//   codesign -s - -f spikes/out/CalendarDump   # ad-hoc подпись
//   spikes/out/CalendarDump > spikes/out/calendar_swift.json
//
// Запускать в своём терминале (промпт macOS). osascript для календаря не рекомендуется.
import EventKit
import Foundation

let store = EKEventStore()
let sem = DispatchSemaphore(value: 0)
var ok = false
store.requestFullAccessToEvents { granted, _ in ok = granted; sem.signal() }
sem.wait()
guard ok else {
    FileHandle.standardError.write("access denied, status=\(EKEventStore.authorizationStatus(for: .event).rawValue)\n".data(using: .utf8)!)
    exit(2)
}
let now = Date()
let start = now.addingTimeInterval(-30 * 86400)
let end = now.addingTimeInterval(14 * 86400)
let cals = store.calendars(for: .event)
let events = store.events(matching: store.predicateForEvents(withStart: start, end: end, calendars: cals))
let iso = ISO8601DateFormatter()
let rows: [[String: Any]] = events.map { e in
    let me = e.attendees?.first(where: { $0.isCurrentUser })
    return [
        "eventIdentifier": e.eventIdentifier ?? NSNull(),
        "calendarItemIdentifier": e.calendarItemIdentifier,
        "calendar": e.calendar.calendarIdentifier,
        "title": e.title ?? "",
        "start": iso.string(from: e.startDate),
        "end": iso.string(from: e.endDate),
        "isAllDay": e.isAllDay,
        "status": e.status.rawValue,
        "availability": e.availability.rawValue,
        "hasRecurrenceRules": e.hasRecurrenceRules,
        "occurrenceDate": e.occurrenceDate.map { iso.string(from: $0) } ?? NSNull(),
        "myParticipation": me?.participantStatus.rawValue ?? -1,
        "hasOrganizer": e.organizer != nil,
        "timeZone": e.timeZone?.identifier ?? NSNull(),
    ]
}
let data = try JSONSerialization.data(withJSONObject: ["events": rows], options: [.prettyPrinted])
FileHandle.standardOutput.write(data)
