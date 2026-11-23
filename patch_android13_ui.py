from pathlib import Path
p = Path('app/src/main/java/ro/ecranviu/ceasblocat/MainActivity.java')
s = p.read_text(encoding='utf-8')
old = '''        addButton("Permite afișarea pe ecran complet", v -> {
            if (Build.VERSION.SDK_INT >= 34) {
                Intent i = new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT);
                i.setData(Uri.parse("package:" + getPackageName()));
                try { startActivity(i); }
                catch (Exception e) { info.setText("Setarea nu este disponibilă pe acest dispozitiv."); }
            } else {
                info.setText("Pe versiunea actuală Android nu există această setare separată.");
            }
        });'''
new = '''        if (Build.VERSION.SDK_INT >= 34) {
            addButton("Permite notificări pe ecran complet", v -> {
                Intent i = new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT);
                i.setData(Uri.parse("package:" + getPackageName()));
                try { startActivity(i); }
                catch (Exception e) { info.setText("Dispozitivul nu oferă această setare. Afișarea depinde de regulile Android."); }
            });
        } else {
            container.addView(text("Android 13 sau mai vechi: nu există o setare separată pentru notificări pe ecran complet. Nu este o eroare; Android le gestionează automat.", 14, Color.LTGRAY));
        }
        container.addView(text("Ecran Viu nu apare la «Afișare deasupra altor aplicații», deoarece nu solicită permisiunea de suprapunere. Nu este necesară.", 14, Color.LTGRAY));'''
if old not in s:
    raise SystemExit("Expected UI code not found, refusing to patch")
s = s.replace(old,new)
oldstatus = '''            "\\nEcran complet: " + (fullScreen ? "permis" : "NEPERMIS") +'''
newstatus = '''            "\\nEcran complet: " + (Build.VERSION.SDK_INT < 34 ? "gestionat de Android" :
                (fullScreen ? "permis" : "NEPERMIS")) +'''
if oldstatus not in s:
    raise SystemExit("Expected status not found")
s = s.replace(oldstatus,newstatus)
s = s.replace('Dacă nu pornește ecranul, verifică cele două permisiuni de afișare.', 'Dacă nu pornește ecranul, verifică notificările și restricțiile de baterie.')
p.write_text(s,encoding='utf-8')
p2=Path('app/build.gradle')
s=p2.read_text()
if "versionCode 1" not in s: raise SystemExit("Wrong Gradle version")
s=s.replace("versionCode 1","versionCode 2").replace("versionName '1.0'","versionName '1.1'")
p2.write_text(s)
print("Applied Android 13 compatible UI and versionCode 2")
