/**
 * Capacitor configuration — used by `npx cap sync` on a Mac (for iOS) or
 * any machine with Android Studio (for Android) to wrap the SaloneHCM
 * PWA into a native iOS / Android bundle that can be submitted to the App
 * Store and Google Play.
 *
 * webDir points at the CRA build output. The native shell loads that
 * directory as its assets, so every improvement made to the web codebase
 * ships to the native app on the next `yarn build && npx cap sync`.
 *
 * server.url makes the native app load the LIVE preview / production URL
 * during development instead of the local build. Comment it out for a
 * production submission so the native binary works fully offline until
 * it hits an /api/* endpoint.
 */
import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.emergent.salonehcm",
  appName: "SaloneHCM",
  webDir: "build",
  bundledWebRuntime: false,

  // Uncomment during dev to point the native shell at the live web build
  // instead of shipped assets — hot-reload without rebuilding native.
  // server: {
  //   url: "https://salonepaycms.preview.emergentagent.com",
  //   cleartext: false,
  // },

  ios: {
    contentInset: "always",
    limitsNavigationsToAppBoundDomains: true,
  },
  android: {
    allowMixedContent: false,
    backgroundColor: "#0A4A1E",
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      launchShowDuration: 1500,
      backgroundColor: "#0A4A1E",
      androidSplashResourceName: "splash",
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    LocalNotifications: {
      smallIcon: "ic_stat_icon",
      iconColor: "#0A4A1E",
    },
  },
};

export default config;
