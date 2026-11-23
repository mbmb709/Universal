from pathlib import Path
pkg=Path("app/src/main/java/ro/ecranviu/ceasblocat")
manifest=Path("app/src/main/AndroidManifest.xml")
s=manifest.read_text(encoding="utf-8")
anchor='        <service android:name=".MonitorService"'
assert anchor in s, "Expected foreground service missing"
receiver='''        <!-- Only force-lock policy, no password/accessibility/data access. Must be enabled manually. -->
        <receiver android:name=".ScreenOffAdminReceiver"
            android:exported="true"
            android:permission="android.permission.BIND_DEVICE_ADMIN">
            <meta-data android:name="android.app.device_admin"
                android:resource="@xml/screen_off_admin" />
            <intent-filter>
                <action android:name="android.app.action.DEVICE_ADMIN_ENABLED" />
            </intent-filter>
        </receiver>
'''
s=s.replace(anchor,receiver+anchor,1)
manifest.write_text(s,encoding="utf-8")

res=Path("app/src/main/res/xml")
res.mkdir(parents=True,exist_ok=True)
(res/"screen_off_admin.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<device-admin xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-policies><force-lock /></uses-policies>
</device-admin>
''',encoding="utf-8")
(pkg/"ScreenOffAdminReceiver.java").write_text('''package ro.ecranviu.ceasblocat;

import android.app.admin.DeviceAdminReceiver;
import android.app.admin.DevicePolicyManager;
import android.content.ComponentName;
import android.content.Context;

public final class ScreenOffAdminReceiver extends DeviceAdminReceiver {
    public static ComponentName component(Context c) {
        return new ComponentName(c, ScreenOffAdminReceiver.class);
    }
    public static boolean isEnabled(Context c) {
        DevicePolicyManager dpm = (DevicePolicyManager) c.getSystemService(Context.DEVICE_POLICY_SERVICE);
        return dpm != null && dpm.isAdminActive(component(c));
    }
    public static void turnScreenOff(Context c) {
        DevicePolicyManager dpm = (DevicePolicyManager) c.getSystemService(Context.DEVICE_POLICY_SERVICE);
        if (dpm != null && dpm.isAdminActive(component(c))) {
            try {
                dpm.lockNow();
            } catch (SecurityException ignored) {
                // Do not crash; the Android system may revoke device administration at any time.
            }
        }
    }
}
''',encoding="utf-8")

p=pkg/"ClockActivity.java"
s=p.read_text(encoding="utf-8")
old='''    private void closeClock() {
        handler.removeCallbacks(update);
        if (!isTest) {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            NotificationManager nm = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
            if (nm!=null) nm.cancel(AlarmReceiver.NOTIFICATION_ID);
        }
        finish();
    }'''
new='''    private void closeClock() {
        handler.removeCallbacks(update);
        // Never switch the screen off during "Mod test".
        boolean turnOff = !isTest && ScreenOffAdminReceiver.isEnabled(this);
        if (!isTest) {
            // Stop keeping the display awake. The clock never dismisses the keyguard.
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            NotificationManager nm = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
            if (nm!=null) nm.cancel(AlarmReceiver.NOTIFICATION_ID);
        }
        finish();
        if (turnOff) {
            // Let the clock Activity finish before requesting an immediate screen lock.
            // Application context avoids retaining the finished Activity.
            final android.content.Context app = getApplicationContext();
            new Handler(Looper.getMainLooper()).postDelayed(
                () -> ScreenOffAdminReceiver.turnScreenOff(app), 180L);
        }
        // Without optional device administrator access Android will use its normal
        // lock-screen timeout. An unprivileged app cannot force the screen off.
    }'''
assert old in s, "Expected ClockActivity closeClock method missing"
s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")

p=pkg/"MainActivity.java"
s=p.read_text(encoding="utf-8")
anchor='        addButton("Pornește afișările", v -> {'
assert anchor in s, "Expected start button missing"
inject='''        addButton("Activează stingerea imediată (opțional)", v -> {
            if (ScreenOffAdminReceiver.isEnabled(this)) {
                info.setText("Stingerea imediată este deja activată. Ceasul va opri ecranul după durata setată.");
                return;
            }
            android.app.admin.DevicePolicyManager dpm =
                (android.app.admin.DevicePolicyManager) getSystemService(DEVICE_POLICY_SERVICE);
            if (dpm == null) {
                info.setText("Telefonul nu oferă administrarea necesară pentru stingerea imediată.");
                return;
            }
            Intent i = new Intent(android.app.admin.DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN);
            i.putExtra(android.app.admin.DevicePolicyManager.EXTRA_DEVICE_ADMIN,
                ScreenOffAdminReceiver.component(this));
            i.putExtra(android.app.admin.DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                "Ecran Viu folosește numai dreptul de blocare pentru a stinge ecranul automat când expiră ceasul. Nu cere acces la parole, contacte sau fișiere. Poți dezactiva oricând.");
            try { startActivity(i); }
            catch (Exception e) {
                info.setText("Android nu a putut afișa cererea pentru stingerea imediată.");
            }
        });
        addButton("Dezactivează stingerea imediată", v -> {
            android.app.admin.DevicePolicyManager dpm =
                (android.app.admin.DevicePolicyManager) getSystemService(DEVICE_POLICY_SERVICE);
            if (dpm != null && dpm.isAdminActive(ScreenOffAdminReceiver.component(this))) {
                try {
                    dpm.removeActiveAdmin(ScreenOffAdminReceiver.component(this));
                    info.setText("Stingerea imediată a fost dezactivată. Android va stinge ecranul după timpul obișnuit.");
                } catch (SecurityException e) {
                    info.setText("Nu se poate dezactiva aici. Folosește Setări → Securitate → Administratori dispozitiv.");
                }
            } else info.setText("Stingerea imediată era deja dezactivată.");
        });
        container.addView(text("Stingere imediată: Android cere permisiunea Administrator dispozitiv, numai cu politica «Blochează ecranul». Fără ea, ecranul poate rămâne aprins până expiră timpul de blocare al telefonului. Activarea este opțională și nu se face automat.", 14, Color.LTGRAY));
'''
s=s.replace(anchor,inject+anchor,1)
# Replace misleading permission statement, regardless of preceding updates.
s=s.replace('Fără internet, contacte, fișiere, cameră, administrator sau accesibilitate. Suprapunerea este solicitată separat, doar cu acordul tău. Serviciul permanent poate crește consumul bateriei.',
'''Fără acces la internet, contacte, fișiere sau cameră. Administratorul dispozitivului este opțional, exclusiv pentru stingerea ecranului; permisiunea de suprapunere este tot opțională. Serviciul din fundal poate crește consumul bateriei.''')
# Explicitly surface the optional admin status in the main screen.
status='''            "\\nSuprapunere: " + (Settings.canDrawOverlays(this) ? "permisă" : "nepermisă") +'''
if status in s:
    s=s.replace(status,status+'''
            "\\nStingere imediată: " + (ScreenOffAdminReceiver.isEnabled(this) ? "ACTIVĂ" : "neactivată") +''',1)
else:
    # Avoid accidental silent omission; patch intentionally requires the v1.2 UI.
    raise SystemExit("Expected foreground service UI status missing")
p.write_text(s,encoding="utf-8")

p=Path("app/build.gradle")
s=p.read_text(encoding="utf-8")
assert "versionCode 3" in s and "versionName '1.2'" in s, "Unexpected version before 1.3 patch"
p.write_text(s.replace("versionCode 3","versionCode 4").replace("versionName '1.2'","versionName '1.3'"),encoding="utf-8")
print("Ecran Viu 1.3: optional force-lock policy, manual consent, off after clock duration, Test Mode untouched")
