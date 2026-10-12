enum AppRoute {
    case threads
    case thread(id: String)
    case settings(SettingsRoute)
}

enum SettingsRoute {
    case notifications
    case about
}
