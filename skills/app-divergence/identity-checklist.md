# App identity checklist

Used by the `app-divergence` skill, step 8, before a fork ships. Every row
was a real defect or a near miss when a fork moved to its own identity and
backend. Walk it with the user; most rows need someone with access to a
console (Apple Developer, Firebase, the backend).

## In the project

- [ ] Identity in **one** place (an `.xcconfig` read by the project
      generator): bundle id, team, display name, versions. Changes made in
      Xcode's General tab are lost on the next generation.
- [ ] Backend host per configuration; the release build points at the
      production host over https.
- [ ] The app name the client sends (request parameters, User-Agent, web
      page queries) is one constant, set to the new app.
- [ ] `GoogleService-Info.plist` from the new Firebase project, with
      `BUNDLE_ID` equal to the built bundle id (push and App Check depend on
      it); APNs key uploaded to that project.
- [ ] Google Sign-In: `GIDClientID` and the reversed-client-id URL scheme
      from the new plist.
- [ ] URL schemes, the router's schemes and associated domains renamed;
      the old app's domains removed.
- [ ] Entitlements (push environment, Sign in with Apple, associated
      domains, time-sensitive notifications) match capabilities enabled on
      the App ID, and the provisioning profile was regenerated after
      enabling them (`codesign -d --entitlements - <app>` shows them).
- [ ] App icon 1024×1024 **without alpha**; no trace of the original's art.
- [ ] Permission texts (`NSCameraUsageDescription` …) name the new app.
- [ ] Every third-party SDK key belongs to the new app; SDKs the fork does
      not use are removed, not left configured with the original's keys.
- [ ] Dependencies build at the app's minimum iOS (for CocoaPods, a
      `post_install` that sets every pod's deployment target to the app's;
      raising pods to the newest SDK breaks older devices).
- [ ] No temporary debug code: key dumps, forced flags, commented-out checks.

## On the backend (ask the backend owner)

- [ ] Sign in with Apple: the accepted audiences include **every** bundle id
      that will sign in (test and release), on production and staging.
- [ ] Google sign-in: the accepted client ids include the new Firebase
      project's.
- [ ] Email or SMS codes: a sender is configured for the new app.
- [ ] Settings and launch endpoints answer for the new app name (not 500),
      and registration flags are chosen on purpose.
- [ ] Endpoint, socket and channel names match the agreed rename list.

## On test devices

- [ ] After switching backends, delete the app and reset its Keychain
      entries (simulator: `xcrun simctl keychain <udid> reset`): a device id
      stored for the old backend makes the new one reject the device.
