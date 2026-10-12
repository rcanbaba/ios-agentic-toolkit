final class Router {
    static let shared = Router()
    private(set) var stack: [AppRoute] = []

    func navigate(to route: AppRoute) {
        stack.append(route)
    }

    func pop() {
        _ = stack.popLast()
    }
}
