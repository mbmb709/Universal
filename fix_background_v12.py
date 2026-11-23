from pathlib import Path

root = Path("app/src/main")
pkg = root / "java/ro/ecranviu/ceasblocat"
manifest = root / "AndroidManifest.xml"
s = manifest.read_text(encoding="utf-8")
anchor = '    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />'
assert anchor in s, "Missing manifest permission anchor"
s = s.replace(anchor, anchor + '''
    <!-- Explicit, user-facing foreground monitoring; no network or data access. -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <!-- Optional grant by user; enables direct lockscreen clock launch on Android 13. -->
    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />''')
s = s.replace('android:excludeFromRecents="true" />',
              'android:excludeFromRecents="true" android:launchMode="singleTop" />')
anchor2 = '        <receiver android:name=".AlarmReceiver" android:exported="false" />'
assert anchor2 in s, "Missing manifest component anchor"
s = s.replace(anchor2, '''        <service android:name=".MonitorService" android:exported="false"
            android:foregroundServiceType="specialUse">
            <property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
                android:value="User-initiated recurring lockscreen clock display monitoring" />
        </service>
''' + anchor2)
manifest.write_text(s,encoding="utf-8")

(pkg/"MonitorService.java").write_text(r'''package ro.ecranviu.ceasblocat;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

public final class MonitorService extends Service {
    static final String ACTION_START = "ro.ecranviu.ceasblocat.START";
    static final int NOTIFICATION_ID = 70;
    static final String CHANNEL_ID = "ecranviu_monitor_v1";
    static volatile boolean running = false;

    @Override public void onCreate() {
        super.onCreate();
        if (ClockSettings.enabled(this)) startMonitoringNotification();
        else stopSelf();
    }

    private void startMonitoringNotification() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null && Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID,
                "Monitorizare Ecran Viu", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Serviciul activ pentru afisarea orei la intervale");
            nm.createNotificationChannel(channel);
        }

        Intent open = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pending = PendingIntent.getActivity(this, 70, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification note = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
                .setContentTitle("Ecran Viu este activ")
                .setContentText("Ceasul va fi afisat periodic cand telefonul este blocat")
                .setContentIntent(pending)
                .setCategory(Notification.CATEGORY_SERVICE)
                .setOngoing(true)
                .build();
        if (Build.VERSION.SDK_INT >= 34)
            startForeground(NOTIFICATION_ID, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else
            startForeground(NOTIFICATION_ID, note);
        running = true;
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (!ClockSettings.enabled(this)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!running) startMonitoringNotification();
        // Keep the service visible and recurring alarm armed even after reopening the app.
        AlarmScheduler.schedule(this);
        return START_STICKY;
    }

    @Override public void onTaskRemoved(Intent rootIntent) {
        if (ClockSettings.enabled(this)) AlarmScheduler.schedule(this);
        super.onTaskRemoved(rootIntent);
    }

    @Override public void onDestroy() {
        running = false;
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
''',encoding="utf-8")

p = pkg/"MainActivity.java"
s = p.read_text(encoding="utf-8")
start = '        addButton("Pornește afișările", v -> {'
assert start in s, "Missing start button"
additional = '''        addButton("Permite afișarea peste alte aplicații (opțional)", v -> {
            if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
                Intent i = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
                try { startActivity(i); }
                catch (Exception e) { info.setText("Deschide manual Setări → Aplicații → Acces special → Afișare deasupra altor aplicații."); }
            } else {
                info.setText("Suprapunerea este deja permisă. Ajută la deschiderea ceasului în fundal pe Android 13.");
            }
        });
        container.addView(text("Această permisiune este opțională și permite aplicației să deschidă ceasul când este în fundal. Nu este folosită pentru reclame.", 14, Color.LTGRAY));
        addButton("Setări baterie · alege Nerestricționat", v -> {
            Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.parse("package:" + getPackageName()));
            try { startActivity(i); }
            catch (Exception e) { info.setText("Setări → Aplicații → Ecran Viu → Baterie → Nerestricționat."); }
        });
        addButton("Testează afișarea timpului acum", v ->
            startActivity(new Intent(this, ClockActivity.class).putExtra("test", false)));
'''
s=s.replace(start, additional+start,1)
old='''            ClockSettings.get(this).edit().putBoolean("enabled", true).apply();
            AlarmScheduler.schedule(this);
            info.setText(permissionStatus());'''
new='''            ClockSettings.get(this).edit().putBoolean("enabled", true).apply();
            try {
                Intent service = new Intent(this, MonitorService.class).setAction(MonitorService.ACTION_START);
                if (Build.VERSION.SDK_INT >= 26) startForegroundService(service);
                else startService(service);
                AlarmScheduler.schedule(this);
                info.setText(permissionStatus() + "\\nServiciul de fundal a fost pornit.");
            } catch (Exception ex) {
                ClockSettings.get(this).edit().putBoolean("enabled", false).apply();
                info.setText("Android a refuzat pornirea serviciului. Verifică notificările și bateria: " + ex.getClass().getSimpleName());
            }'''
assert old in s, "Missing old start logic"
s=s.replace(old,new,1)
oldstop='''            AlarmScheduler.cancel(this);
            NotificationManager nm'''
newstop='''            AlarmScheduler.cancel(this);
            stopService(new Intent(this, MonitorService.class));
            NotificationManager nm'''
assert oldstop in s
s=s.replace(oldstop,newstop,1)
s=s.replace('''            "\\nNotificări: " + (notifications ? "permise" : "NEPERMISE") +''',
'''            "\\nServiciu fundal: " + (MonitorService.running ? "activ" : "oprit") +
            "\\nSuprapunere: " + (Settings.canDrawOverlays(this) ? "permisă" : "nepermisă") +
            "\\nNotificări: " + (notifications ? "permise" : "NEPERMISE") +''')
s=s.replace('''container.addView(text("Fără internet, contacte, fișiere, cameră, administrator, accesibilitate sau permisiunea de afișare peste alte aplicații.", 14, Color.LTGRAY));''',
'''container.addView(text("Fără internet, contacte, fișiere, cameră, administrator sau accesibilitate. Suprapunerea este solicitată separat, doar cu acordul tău. Serviciul permanent poate crește consumul bateriei.", 14, Color.LTGRAY));''')
s=s.replace('''container.addView(text("Telefonul rămâne BLOCAT. Afișarea programată folosește sistemul de alarme Android, nu administrator de dispozitiv.", 15, Color.LTGRAY));''',
'''container.addView(text("Telefonul rămâne BLOCAT. Serviciul de fundal afișează ceasul folosind alarme Android. O notificare permanentă arată când serviciul rulează.", 15, Color.LTGRAY));''')
s=s.replace('''container.addView(text("LIMITĂ ANDROID: dacă notificările pe ecran complet nu sunt permise, ceasul poate apărea doar ca notificare. Alarmele pot întârzia când telefonul economisește bateria. La final, se revine la ecranul blocat; stingerea lui exact la secundă depinde de setările sistemului.", 14, Color.LTGRAY));''',
'''container.addView(text("LIMITĂ ANDROID: Samsung poate întârzia alarmele în Doze, chiar cu serviciu în fundal. Când ceasul se închide, ecranul revine la blocare; stingerea exactă depinde de sistem. Pentru stabilitate, setează bateria la Nerestricționat.", 14, Color.LTGRAY));''')
# The MainActivity runs in the same process; onResume gets accurate service state.
p.write_text(s, encoding="utf-8")

p=pkg/"BootReceiver.java"
s=p.read_text(encoding="utf-8")
old='''        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction()))
            AlarmScheduler.schedule(context);'''
new='''        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction()) && ClockSettings.enabled(context)) {
            AlarmScheduler.schedule(context);
            try {
                Intent service = new Intent(context, MonitorService.class).setAction(MonitorService.ACTION_START);
                if (android.os.Build.VERSION.SDK_INT >= 26) context.startForegroundService(service);
                else context.startService(service);
            } catch (RuntimeException ignored) {
                // Android versions can restrict background service starts after boot.
                // AlarmManager remains armed as the safe fallback.
            }
        }'''
assert old in s
p.write_text(s.replace(old,new),encoding="utf-8")

p=pkg/"AlarmReceiver.java"
s=p.read_text(encoding="utf-8")
s=s.replace('import android.app.ActivityOptions;', '''import android.app.ActivityOptions;
import android.app.KeyguardManager;''')
s=s.replace('import android.os.Build;', '''import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;''')
old='''        AlarmScheduler.schedule(context); // recurring; no permanent background service
        createChannel(context);
        if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) return;
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || !nm.areNotificationsEnabled()) return;

        Intent show = new Intent(context, ClockActivity.class)
                .putExtra("test", false)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);'''
new='''        AlarmScheduler.schedule(context); // keep next alarm armed
        PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        KeyguardManager kg = (KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);
        boolean screenOff = pm == null || !pm.isInteractive();
        boolean locked = kg != null && kg.isKeyguardLocked();
        if (!screenOff && !locked) return; // never interrupt normal phone use

        PowerManager.WakeLock wake = null;
        if (pm != null) {
            wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "EcranViu:ShowClock");
            wake.acquire(5000L); // short timeout; no perpetual CPU wake lock
        }
        try {
            createChannel(context);
            Intent show = new Intent(context, ClockActivity.class)
                .putExtra("test", false)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

            // Android 13 permits user-approved overlay apps to launch an Activity from
            // the background. On newer versions the system may forbid this.
            if (Build.VERSION.SDK_INT < 35 && Settings.canDrawOverlays(context)) {
                try { context.startActivity(show); }
                catch (RuntimeException ignored) { /* full-screen notification is fallback */ }
            }
            if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) return;
            NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null || !nm.areNotificationsEnabled()) return;'''
assert old in s, "Missing original alarm core"
s=s.replace(old,new,1)
old_tail='''        nm.notify(NOTIFICATION_ID, notice);
    }
}'''
new_tail='''            nm.notify(NOTIFICATION_ID, notice);
        } finally {
            if (wake != null && wake.isHeld()) wake.release();
        }
    }
}'''
assert old_tail in s, "Missing alarm tail"
s=s.replace(old_tail,new_tail,1)
p.write_text(s,encoding="utf-8")

# v1.1 used versionCode 2 (from Android 13 UI fix). This update is 3.
p=Path("app/build.gradle")
s=p.read_text(encoding="utf-8")
assert "versionCode 2" in s, "Wrong app version before patch"
p.write_text(s.replace("versionCode 2", "versionCode 3").replace("versionName '1.1'", "versionName '1.2'"),encoding="utf-8")
print("Foreground service, optional overlay, timed wake lock, Android 13 UI and version 1.2: patched.")
