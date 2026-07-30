export interface SystemToolsTranslation {
  systemTools: string;
  systemToolsDescription: string;
  systemToolsStatus: string;
  systemToolsLoading: string;
  mangoHudFix: string;
  mangoHudFixDescription: string;
  mangoHudFixInstalled: string;
  mangoHudFixNeedsRepair: string;
  mangoHudFixNotInstalled: string;
  mangoHudFixUnavailable: string;
  installOrRepairMangoHudFix: string;
  removeMangoHudFix: string;
  mangoHudFixApplied: string;
  mangoHudFixRemoved: string;
  steamOsApplication: string;
  steamOsApplicationDescription: string;
  addOrRepairSteamOsApplication: string;
  steamOsApplicationReady: string;
  nestedDesktopMouseBridge: string;
  nestedDesktopMouseBridgeDescription: string;
  nestedDesktopTrackpadInertia: string;
  nestedDesktopTrackpadInertiaDescription: string;
  rustDeskPointerFix: string;
  rustDeskPointerFixDescription: string;
  rustDeskFocusOnInput: string;
  rustDeskFocusOnInputDescription: string;
  rustDeskScrollInertia: string;
  rustDeskScrollInertiaDescription: string;
  controller: string;
  trackpadAutoRecovery: string;
  trackpadAutoRecoveryDescription: string;
}

type BaseSystemToolsTranslation = Omit<
  SystemToolsTranslation,
  | "rustDeskFocusOnInput"
  | "rustDeskFocusOnInputDescription"
  | "rustDeskScrollInertia"
  | "rustDeskScrollInertiaDescription"
  | "controller"
  | "trackpadAutoRecovery"
  | "trackpadAutoRecoveryDescription"
>;

type Values = [
  systemTools: string,
  systemToolsDescription: string,
  systemToolsStatus: string,
  systemToolsLoading: string,
  mangoHudFix: string,
  mangoHudFixDescription: string,
  mangoHudFixInstalled: string,
  mangoHudFixNeedsRepair: string,
  mangoHudFixNotInstalled: string,
  mangoHudFixUnavailable: string,
  installOrRepairMangoHudFix: string,
  removeMangoHudFix: string,
  mangoHudFixApplied: string,
  mangoHudFixRemoved: string,
  steamOsApplication: string,
  steamOsApplicationDescription: string,
  addOrRepairSteamOsApplication: string,
  steamOsApplicationReady: string,
  nestedDesktopMouseBridge: string,
  nestedDesktopMouseBridgeDescription: string,
  nestedDesktopTrackpadInertia: string,
  nestedDesktopTrackpadInertiaDescription: string,
  rustDeskPointerFix: string,
  rustDeskPointerFixDescription: string,
];

const define = ([
  systemTools,
  systemToolsDescription,
  systemToolsStatus,
  systemToolsLoading,
  mangoHudFix,
  mangoHudFixDescription,
  mangoHudFixInstalled,
  mangoHudFixNeedsRepair,
  mangoHudFixNotInstalled,
  mangoHudFixUnavailable,
  installOrRepairMangoHudFix,
  removeMangoHudFix,
  mangoHudFixApplied,
  mangoHudFixRemoved,
  steamOsApplication,
  steamOsApplicationDescription,
  addOrRepairSteamOsApplication,
  steamOsApplicationReady,
  nestedDesktopMouseBridge,
  nestedDesktopMouseBridgeDescription,
  nestedDesktopTrackpadInertia,
  nestedDesktopTrackpadInertiaDescription,
  rustDeskPointerFix,
  rustDeskPointerFixDescription,
]: Values): BaseSystemToolsTranslation => ({
  systemTools,
  systemToolsDescription,
  systemToolsStatus,
  systemToolsLoading,
  mangoHudFix,
  mangoHudFixDescription,
  mangoHudFixInstalled,
  mangoHudFixNeedsRepair,
  mangoHudFixNotInstalled,
  mangoHudFixUnavailable,
  installOrRepairMangoHudFix,
  removeMangoHudFix,
  mangoHudFixApplied,
  mangoHudFixRemoved,
  steamOsApplication,
  steamOsApplicationDescription,
  addOrRepairSteamOsApplication,
  steamOsApplicationReady,
  nestedDesktopMouseBridge,
  nestedDesktopMouseBridgeDescription,
  nestedDesktopTrackpadInertia,
  nestedDesktopTrackpadInertiaDescription,
  rustDeskPointerFix,
  rustDeskPointerFixDescription,
});

const baseSystemToolsTranslations:
Record<string, BaseSystemToolsTranslation> = {
  arabic: define([
    "أدوات النظام", "تثبيت وإدارة إصلاحات نظام محددة", "الحالة", "جارٍ التحميل…",
    "إصلاح MangoHud لسطح المكتب المتداخل", "يمنع عمليات سطح المكتب المتداخل المحمية من تعطيل MangoApp وإخفاء تراكب الأداء",
    "مثبّت", "يلزم التحديث أو الإصلاح", "غير مثبّت", "غير متاح على هذا النظام",
    "تثبيت / إصلاح", "إزالة الإصلاح", "تم تثبيت إصلاح MangoHud", "تمت إزالة إصلاح MangoHud",
    "SteamOS في وضع الألعاب", "يضيف أو يصلح اختصار Nested Desktop معدًا بالكامل في مكتبة Steam",
    "إضافة / إصلاح SteamOS", "تطبيق SteamOS جاهز",
    "ماوس Nested Desktop فوق الألعاب", "يعيد مؤشر لوحة التتبع اليمنى والنقر في Nested Desktop عند تشغيل تطبيق آخر في وضع الألعاب",
    "قصور لوحة التتبع", "يستمر تحريك المؤشر والتمرير بعد سحب سريع؛ عطّله للتوقف فور رفع الإصبع عن لوحة التتبع",
    "إصلاح مؤشر RustDesk", "يمنع تكرار المؤشر وانتقاله المفاجئ في Nested Desktop؛ يقوم «إضافة / إصلاح RustDesk» بتثبيت خطاف النظام المطلوب تلقائيًا",
  ]),
  brazilian: define([
    "Ferramentas do sistema", "Instale e gerencie correções específicas do sistema", "Status", "Carregando…",
    "Correção do MangoHud para Nested Desktop", "Impede que processos protegidos do Nested Desktop encerrem o MangoApp e ocultem a sobreposição de desempenho",
    "Instalado", "Atualização ou reparo necessário", "Não instalado", "Indisponível neste sistema",
    "Instalar / Reparar", "Remover correção", "Correção do MangoHud instalada", "Correção do MangoHud removida",
    "SteamOS no Modo Jogo", "Adiciona ou repara um atalho do Nested Desktop totalmente configurado na biblioteca Steam",
    "Adicionar / Reparar SteamOS", "O aplicativo SteamOS está pronto",
    "Mouse do Nested Desktop sobre jogos", "Restaura o cursor e o clique do trackpad direito no Nested Desktop enquanto outro aplicativo do Modo Jogo está em execução",
    "Inércia do trackpad", "Mantém o movimento do cursor e da rolagem após um gesto rápido; desative para parar imediatamente ao soltar o trackpad",
    "Correção do ponteiro do RustDesk", "Evita cursores duplicados e teletransporte do ponteiro no Nested Desktop; Adicionar / Reparar RustDesk instala automaticamente a integração de sistema necessária",
  ]),
  bulgarian: define([
    "Системни инструменти", "Инсталиране и управление на конкретни системни корекции", "Състояние", "Зареждане…",
    "Корекция на MangoHud за Nested Desktop", "Не позволява на защитени процеси на Nested Desktop да сриват MangoApp и да скриват слоя за производителност",
    "Инсталирана", "Нужно е обновяване или поправяне", "Не е инсталирана", "Не е налична за тази система",
    "Инсталиране / Поправяне", "Премахване на корекцията", "Корекцията на MangoHud е инсталирана", "Корекцията на MangoHud е премахната",
    "SteamOS в игрови режим", "Добавя или поправя напълно настроен ярлик за Nested Desktop в библиотеката на Steam",
    "Добавяне / Поправяне на SteamOS", "Приложението SteamOS е готово",
    "Мишка за Nested Desktop върху игра", "Възстановява курсора и щракването с десния тракпад в Nested Desktop, докато работи друго приложение в игрови режим",
    "Инерция на тракпада", "Продължава движението на курсора и превъртането след бързо плъзване; изключете за незабавно спиране при отпускане на тракпада",
    "Корекция на показалеца на RustDesk", "Предотвратява дублиран курсор и телепортиране на показалеца в Nested Desktop; Добавяне / Поправяне на RustDesk автоматично инсталира нужната системна интеграция",
  ]),
  czech: define([
    "Systémové nástroje", "Instalace a správa cílených systémových oprav", "Stav", "Načítání…",
    "Oprava MangoHud pro Nested Desktop", "Zabrání chráněným procesům Nested Desktop ukončit MangoApp a skrýt překryv výkonu",
    "Nainstalováno", "Je nutná aktualizace nebo oprava", "Nenainstalováno", "V tomto systému není dostupné",
    "Nainstalovat / Opravit", "Odstranit opravu", "Oprava MangoHud byla nainstalována", "Oprava MangoHud byla odstraněna",
    "SteamOS v herním režimu", "Přidá nebo opraví plně nastaveného zástupce Nested Desktop v knihovně Steam",
    "Přidat / Opravit SteamOS", "Aplikace SteamOS je připravena",
    "Myš Nested Desktop nad hrou", "Obnoví kurzor a kliknutí pravého trackpadu v Nested Desktop, když je spuštěna jiná aplikace v herním režimu",
    "Setrvačnost trackpadu", "Po rychlém přejetí pokračuje v pohybu kurzoru a posouvání; vypnutím se pohyb zastaví ihned po uvolnění trackpadu",
    "Oprava ukazatele RustDesk", "Zabraňuje zdvojení kurzoru a přeskakování ukazatele v Nested Desktop; Přidat / Opravit RustDesk automaticky nainstaluje potřebné systémové propojení",
  ]),
  danish: define([
    "Systemværktøjer", "Installer og administrer målrettede systemrettelser", "Status", "Indlæser…",
    "MangoHud-rettelse til Nested Desktop", "Forhindrer beskyttede Nested Desktop-processer i at afslutte MangoApp og skjule ydelsesoverlayet",
    "Installeret", "Opdatering eller reparation kræves", "Ikke installeret", "Ikke tilgængelig på dette system",
    "Installer / Reparer", "Fjern rettelse", "MangoHud-rettelsen er installeret", "MangoHud-rettelsen er fjernet",
    "SteamOS i spiltilstand", "Tilføjer eller reparerer en fuldt konfigureret Nested Desktop-genvej i Steam-biblioteket",
    "Tilføj / Reparer SteamOS", "SteamOS-programmet er klar",
    "Nested Desktop-mus over spil", "Gendanner markøren og klik med højre pegefelt i Nested Desktop, mens en anden app kører i spiltilstand",
    "Pegefeltets inerti", "Fortsætter markør- og rullebevægelse efter et hurtigt strøg; deaktiver for at stoppe med det samme, når pegefeltet slippes",
    "RustDesk-markørrettelse", "Forhindrer dobbelte markører og springende markør i Nested Desktop; Tilføj / Reparer RustDesk installerer automatisk den nødvendige systemintegration",
  ]),
  dutch: define([
    "Systeemhulpmiddelen", "Gerichte systeemoplossingen installeren en beheren", "Status", "Laden…",
    "MangoHud-oplossing voor Nested Desktop", "Voorkomt dat beveiligde Nested Desktop-processen MangoApp laten crashen en de prestatie-overlay verbergen",
    "Geïnstalleerd", "Bijwerken of herstellen vereist", "Niet geïnstalleerd", "Niet beschikbaar op dit systeem",
    "Installeren / Herstellen", "Oplossing verwijderen", "MangoHud-oplossing geïnstalleerd", "MangoHud-oplossing verwijderd",
    "SteamOS in gamemodus", "Voegt een volledig ingestelde Nested Desktop-snelkoppeling toe aan de Steam-bibliotheek of herstelt deze",
    "SteamOS toevoegen / herstellen", "De SteamOS-toepassing is gereed",
    "Nested Desktop-muis boven games", "Herstelt de cursor en klik van de rechtertrackpad in Nested Desktop terwijl een andere gamemodus-app actief is",
    "Trackpadtraagheid", "Laat cursor en scrollen doorgaan na een snelle veeg; schakel uit om direct te stoppen zodra de trackpad wordt losgelaten",
    "RustDesk-aanwijzercorrectie", "Voorkomt dubbele cursors en verspringen van de aanwijzer in Nested Desktop; RustDesk toevoegen / herstellen installeert automatisch de vereiste systeemkoppeling",
  ]),
  finnish: define([
    "Järjestelmätyökalut", "Asenna ja hallitse rajattuja järjestelmäkorjauksia", "Tila", "Ladataan…",
    "MangoHud-korjaus Nested Desktopille", "Estää suojattuja Nested Desktop -prosesseja kaatamasta MangoAppia ja piilottamasta suorituskykypeittokuvaa",
    "Asennettu", "Päivitys tai korjaus vaaditaan", "Ei asennettu", "Ei käytettävissä tässä järjestelmässä",
    "Asenna / Korjaa", "Poista korjaus", "MangoHud-korjaus asennettu", "MangoHud-korjaus poistettu",
    "SteamOS pelitilassa", "Lisää tai korjaa täysin määritetyn Nested Desktop -pikakuvakkeen Steam-kirjastossa",
    "Lisää / Korjaa SteamOS", "SteamOS-sovellus on valmis",
    "Nested Desktop -hiiri pelin päällä", "Palauttaa oikean ohjauslevyn osoittimen ja napsautuksen Nested Desktopissa, kun toinen pelitilan sovellus on käynnissä",
    "Ohjauslevyn inertia", "Jatkaa osoittimen ja vierityksen liikettä nopean pyyhkäisyn jälkeen; poista käytöstä, jos haluat pysäyttää heti ohjauslevyn vapautuessa",
    "RustDesk-osoittimen korjaus", "Estää kaksoiskohdistimet ja osoittimen hyppimisen Nested Desktopissa; Lisää / Korjaa RustDesk asentaa tarvittavan järjestelmäintegraation automaattisesti",
  ]),
  french: define([
    "Outils système", "Installer et gérer des correctifs système ciblés", "État", "Chargement…",
    "Correctif MangoHud pour Nested Desktop", "Empêche les processus protégés de Nested Desktop de faire planter MangoApp et de masquer l’overlay de performances",
    "Installé", "Mise à jour ou réparation requise", "Non installé", "Indisponible sur ce système",
    "Installer / Réparer", "Supprimer le correctif", "Correctif MangoHud installé", "Correctif MangoHud supprimé",
    "SteamOS en mode jeu", "Ajoute ou répare un raccourci Nested Desktop entièrement configuré dans la bibliothèque Steam",
    "Ajouter / Réparer SteamOS", "L’application SteamOS est prête",
    "Souris de Nested Desktop sur un jeu", "Rétablit le curseur et le clic du pavé tactile droit dans Nested Desktop lorsqu’une autre application du mode Jeu est en cours d’exécution",
    "Inertie du pavé tactile", "Prolonge le mouvement du curseur et du défilement après un geste rapide ; désactivez-la pour arrêter dès que le pavé tactile est relâché",
    "Correctif du pointeur RustDesk", "Évite les curseurs en double et les téléportations du pointeur dans Nested Desktop ; Ajouter / Réparer RustDesk installe automatiquement l’intégration système requise",
  ]),
  german: define([
    "Systemwerkzeuge", "Gezielte Systemkorrekturen installieren und verwalten", "Status", "Wird geladen…",
    "MangoHud-Korrektur für Nested Desktop", "Verhindert, dass geschützte Nested-Desktop-Prozesse MangoApp abstürzen lassen und das Leistungs-Overlay ausblenden",
    "Installiert", "Aktualisierung oder Reparatur erforderlich", "Nicht installiert", "Auf diesem System nicht verfügbar",
    "Installieren / Reparieren", "Korrektur entfernen", "MangoHud-Korrektur installiert", "MangoHud-Korrektur entfernt",
    "SteamOS im Gaming-Modus", "Fügt der Steam-Bibliothek eine vollständig konfigurierte Nested-Desktop-Verknüpfung hinzu oder repariert sie",
    "SteamOS hinzufügen / reparieren", "Die SteamOS-Anwendung ist bereit",
    "Nested-Desktop-Maus über Spielen", "Stellt Cursor und Klick des rechten Trackpads in Nested Desktop wieder her, während eine andere Gaming-Modus-App läuft",
    "Trackpad-Trägheit", "Setzt Cursor- und Scrollbewegungen nach schnellem Wischen fort; deaktivieren, um beim Loslassen des Trackpads sofort anzuhalten",
    "RustDesk-Zeigerkorrektur", "Verhindert doppelte Cursor und Zeigersprünge in Nested Desktop; RustDesk hinzufügen / reparieren installiert die erforderliche Systemintegration automatisch",
  ]),
  greek: define([
    "Εργαλεία συστήματος", "Εγκατάσταση και διαχείριση στοχευμένων διορθώσεων συστήματος", "Κατάσταση", "Φόρτωση…",
    "Διόρθωση MangoHud για Nested Desktop", "Αποτρέπει προστατευμένες διεργασίες του Nested Desktop από το να τερματίζουν το MangoApp και να κρύβουν την επικάλυψη επιδόσεων",
    "Εγκατεστημένη", "Απαιτείται ενημέρωση ή επιδιόρθωση", "Δεν είναι εγκατεστημένη", "Δεν είναι διαθέσιμη σε αυτό το σύστημα",
    "Εγκατάσταση / Επιδιόρθωση", "Αφαίρεση διόρθωσης", "Η διόρθωση MangoHud εγκαταστάθηκε", "Η διόρθωση MangoHud αφαιρέθηκε",
    "SteamOS σε λειτουργία παιχνιδιού", "Προσθέτει ή επιδιορθώνει μια πλήρως ρυθμισμένη συντόμευση Nested Desktop στη βιβλιοθήκη Steam",
    "Προσθήκη / Επιδιόρθωση SteamOS", "Η εφαρμογή SteamOS είναι έτοιμη",
    "Ποντίκι Nested Desktop πάνω από παιχνίδι", "Επαναφέρει τον δείκτη και το κλικ του δεξιού trackpad στο Nested Desktop όταν εκτελείται άλλη εφαρμογή σε λειτουργία παιχνιδιού",
    "Αδράνεια trackpad", "Συνεχίζει την κίνηση του δείκτη και την κύλιση μετά από γρήγορη σάρωση· απενεργοποιήστε την για άμεσο σταμάτημα όταν αφήνετε το trackpad",
    "Διόρθωση δείκτη RustDesk", "Αποτρέπει διπλούς δρομείς και τηλεμεταφορά του δείκτη στο Nested Desktop· η Προσθήκη / Διόρθωση RustDesk εγκαθιστά αυτόματα την απαιτούμενη ενσωμάτωση συστήματος",
  ]),
  hungarian: define([
    "Rendszereszközök", "Célzott rendszerjavítások telepítése és kezelése", "Állapot", "Betöltés…",
    "MangoHud-javítás Nested Desktophoz", "Megakadályozza, hogy a Nested Desktop védett folyamatai leállítsák a MangoAppot és elrejtsék a teljesítményréteget",
    "Telepítve", "Frissítés vagy javítás szükséges", "Nincs telepítve", "Ezen a rendszeren nem érhető el",
    "Telepítés / Javítás", "Javítás eltávolítása", "A MangoHud-javítás telepítve", "A MangoHud-javítás eltávolítva",
    "SteamOS játékmódban", "Teljesen beállított Nested Desktop-parancsikont ad a Steam könyvtárhoz, vagy kijavítja azt",
    "SteamOS hozzáadása / javítása", "A SteamOS alkalmazás készen áll",
    "Nested Desktop egér játék fölött", "Visszaállítja a jobb oldali érintőpad kurzorát és kattintását a Nested Desktopban, miközben egy másik játékmód-alkalmazás fut",
    "Érintőpad tehetetlensége", "Egy gyors húzás után tovább mozgatja a kurzort és a görgetést; kikapcsolva az érintőpad elengedésekor azonnal megáll",
    "RustDesk-mutató javítása", "Megakadályozza a kettős kurzort és a mutató ugrálását a Nested Desktopban; a RustDesk hozzáadása / javítása automatikusan telepíti a szükséges rendszerintegrációt",
  ]),
  indonesian: define([
    "Alat sistem", "Instal dan kelola perbaikan sistem yang terarah", "Status", "Memuat…",
    "Perbaikan MangoHud untuk Nested Desktop", "Mencegah proses Nested Desktop yang terlindungi menghentikan MangoApp dan menyembunyikan overlay performa",
    "Terinstal", "Pembaruan atau perbaikan diperlukan", "Belum terinstal", "Tidak tersedia di sistem ini",
    "Instal / Perbaiki", "Hapus perbaikan", "Perbaikan MangoHud terinstal", "Perbaikan MangoHud dihapus",
    "SteamOS dalam Mode Game", "Menambah atau memperbaiki pintasan Nested Desktop yang telah dikonfigurasi penuh di pustaka Steam",
    "Tambah / Perbaiki SteamOS", "Aplikasi SteamOS siap",
    "Mouse Nested Desktop di atas game", "Memulihkan kursor dan klik trackpad kanan di Nested Desktop saat aplikasi Mode Game lain sedang berjalan",
    "Inersia trackpad", "Melanjutkan gerakan kursor dan gulir setelah usapan cepat; nonaktifkan agar langsung berhenti saat trackpad dilepas",
    "Perbaikan penunjuk RustDesk", "Mencegah kursor ganda dan penunjuk berpindah tiba-tiba di Nested Desktop; Tambah / Perbaiki RustDesk memasang integrasi sistem yang diperlukan secara otomatis",
  ]),
  italian: define([
    "Strumenti di sistema", "Installa e gestisci correzioni di sistema mirate", "Stato", "Caricamento…",
    "Correzione MangoHud per Nested Desktop", "Impedisce ai processi protetti di Nested Desktop di arrestare MangoApp e nascondere l’overlay delle prestazioni",
    "Installata", "Aggiornamento o riparazione necessari", "Non installata", "Non disponibile su questo sistema",
    "Installa / Ripara", "Rimuovi correzione", "Correzione MangoHud installata", "Correzione MangoHud rimossa",
    "SteamOS in modalità gioco", "Aggiunge o ripara un collegamento Nested Desktop completamente configurato nella libreria di Steam",
    "Aggiungi / Ripara SteamOS", "L’applicazione SteamOS è pronta",
    "Mouse di Nested Desktop sopra i giochi", "Ripristina il cursore e il clic del trackpad destro in Nested Desktop mentre è in esecuzione un’altra app in modalità gioco",
    "Inerzia del trackpad", "Continua il movimento del cursore e lo scorrimento dopo uno swipe rapido; disattivala per fermarli subito quando rilasci il trackpad",
    "Correzione puntatore RustDesk", "Evita cursori duplicati e salti del puntatore in Nested Desktop; Aggiungi / Ripara RustDesk installa automaticamente l’integrazione di sistema necessaria",
  ]),
  japanese: define([
    "システムツール", "対象を限定したシステム修正をインストールして管理します", "状態", "読み込み中…",
    "Nested Desktop 用 MangoHud 修正", "保護された Nested Desktop プロセスによる MangoApp のクラッシュとパフォーマンスオーバーレイの消失を防ぎます",
    "インストール済み", "更新または修復が必要です", "未インストール", "このシステムでは利用できません",
    "インストール / 修復", "修正を削除", "MangoHud 修正をインストールしました", "MangoHud 修正を削除しました",
    "ゲームモードの SteamOS", "Steam ライブラリに設定済みの Nested Desktop ショートカットを追加または修復します",
    "SteamOS を追加 / 修復", "SteamOS アプリケーションの準備ができました",
    "ゲーム上の Nested Desktop マウス", "別のゲームモードアプリの実行中に、Nested Desktop で右トラックパッドのカーソルとクリックを復元します",
    "トラックパッドの慣性", "素早くスワイプした後もカーソルとスクロールを動かします。トラックパッドを離した瞬間に停止するには無効にします",
    "RustDesk ポインター修正", "Nested Desktop での二重カーソルとポインターの飛びを防ぎます。「RustDesk を追加 / 修復」で必要なシステム連携が自動的にインストールされます",
  ]),
  koreana: define([
    "시스템 도구", "범위가 제한된 시스템 수정 사항을 설치하고 관리합니다", "상태", "불러오는 중…",
    "Nested Desktop용 MangoHud 수정", "보호된 Nested Desktop 프로세스가 MangoApp을 중단시키고 성능 오버레이를 숨기는 문제를 방지합니다",
    "설치됨", "업데이트 또는 복구 필요", "설치되지 않음", "이 시스템에서 사용할 수 없음",
    "설치 / 복구", "수정 제거", "MangoHud 수정이 설치됨", "MangoHud 수정이 제거됨",
    "게임 모드의 SteamOS", "Steam 라이브러리에 완전히 구성된 Nested Desktop 바로 가기를 추가하거나 복구합니다",
    "SteamOS 추가 / 복구", "SteamOS 애플리케이션이 준비되었습니다",
    "게임 위 Nested Desktop 마우스", "다른 게임 모드 앱이 실행 중일 때 Nested Desktop에서 오른쪽 트랙패드 커서와 클릭을 복원합니다",
    "트랙패드 관성", "빠르게 스와이프한 뒤에도 커서와 스크롤 이동을 이어갑니다. 트랙패드에서 손을 떼는 즉시 멈추려면 끄세요",
    "RustDesk 포인터 수정", "Nested Desktop의 이중 커서와 포인터 순간 이동을 방지합니다. RustDesk 추가 / 복구가 필요한 시스템 통합을 자동으로 설치합니다",
  ]),
  latam: define([
    "Herramientas del sistema", "Instala y administra correcciones específicas del sistema", "Estado", "Cargando…",
    "Corrección de MangoHud para Nested Desktop", "Evita que los procesos protegidos de Nested Desktop cierren MangoApp y oculten la superposición de rendimiento",
    "Instalada", "Se requiere actualizar o reparar", "No instalada", "No disponible en este sistema",
    "Instalar / Reparar", "Quitar corrección", "Corrección de MangoHud instalada", "Corrección de MangoHud eliminada",
    "SteamOS en modo juego", "Agrega o repara un acceso directo de Nested Desktop totalmente configurado en la biblioteca de Steam",
    "Agregar / Reparar SteamOS", "La aplicación SteamOS está lista",
    "Mouse de Nested Desktop sobre juegos", "Restaura el cursor y el clic del trackpad derecho en Nested Desktop mientras se ejecuta otra aplicación del modo Juego",
    "Inercia del trackpad", "Mantiene el movimiento del cursor y el desplazamiento después de un deslizamiento rápido; desactívala para detenerlos al soltar el trackpad",
    "Corrección del puntero de RustDesk", "Evita cursores duplicados y saltos del puntero en Nested Desktop; Agregar / Reparar RustDesk instala automáticamente la integración del sistema necesaria",
  ]),
  malay: define([
    "Alat sistem", "Pasang dan urus pembaikan sistem yang disasarkan", "Status", "Memuatkan…",
    "Pembaikan MangoHud untuk Nested Desktop", "Menghalang proses Nested Desktop yang dilindungi daripada meruntuhkan MangoApp dan menyembunyikan tindanan prestasi",
    "Dipasang", "Kemas kini atau pembaikan diperlukan", "Belum dipasang", "Tidak tersedia pada sistem ini",
    "Pasang / Baiki", "Alih keluar pembaikan", "Pembaikan MangoHud dipasang", "Pembaikan MangoHud dialih keluar",
    "SteamOS dalam Mod Permainan", "Menambah atau membaiki pintasan Nested Desktop yang dikonfigurasi sepenuhnya dalam pustaka Steam",
    "Tambah / Baiki SteamOS", "Aplikasi SteamOS sudah sedia",
    "Tetikus Nested Desktop di atas permainan", "Memulihkan kursor dan klik pad jejak kanan dalam Nested Desktop semasa aplikasi Mod Permainan lain sedang berjalan",
    "Inersia pad jejak", "Meneruskan pergerakan kursor dan tatal selepas leretan pantas; nyahdayakan untuk berhenti serta-merta apabila pad jejak dilepaskan",
    "Pembaikan penuding RustDesk", "Menghalang kursor berganda dan penuding melompat dalam Nested Desktop; Tambah / Baiki RustDesk memasang integrasi sistem yang diperlukan secara automatik",
  ]),
  norwegian: define([
    "Systemverktøy", "Installer og administrer målrettede systemrettinger", "Status", "Laster…",
    "MangoHud-retting for Nested Desktop", "Hindrer beskyttede Nested Desktop-prosesser i å krasje MangoApp og skjule ytelsesoverlegget",
    "Installert", "Oppdatering eller reparasjon kreves", "Ikke installert", "Ikke tilgjengelig på dette systemet",
    "Installer / Reparer", "Fjern retting", "MangoHud-rettingen er installert", "MangoHud-rettingen er fjernet",
    "SteamOS i spillmodus", "Legger til eller reparerer en fullstendig konfigurert Nested Desktop-snarvei i Steam-biblioteket",
    "Legg til / Reparer SteamOS", "SteamOS-programmet er klart",
    "Nested Desktop-mus over spill", "Gjenoppretter markøren og klikk med høyre styreflate i Nested Desktop mens en annen spillmodus-app kjører",
    "Styreflateinerti", "Fortsetter markør- og rullebevegelsen etter et raskt sveip; deaktiver for å stoppe umiddelbart når styreflaten slippes",
    "RustDesk-pekerrettelse", "Forhindrer doble markører og pekerhopp i Nested Desktop; Legg til / Reparer RustDesk installerer automatisk den nødvendige systemintegrasjonen",
  ]),
  polish: define([
    "Narzędzia systemowe", "Instaluj i zarządzaj precyzyjnymi poprawkami systemu", "Stan", "Wczytywanie…",
    "Poprawka MangoHud dla Nested Desktop", "Zapobiega awarii MangoApp i ukrywaniu nakładki wydajności przez chronione procesy Nested Desktop",
    "Zainstalowana", "Wymagana aktualizacja lub naprawa", "Niezainstalowana", "Niedostępna w tym systemie",
    "Zainstaluj / Napraw", "Usuń poprawkę", "Poprawka MangoHud została zainstalowana", "Poprawka MangoHud została usunięta",
    "SteamOS w trybie gry", "Dodaje lub naprawia w pełni skonfigurowany skrót Nested Desktop w bibliotece Steam",
    "Dodaj / Napraw SteamOS", "Aplikacja SteamOS jest gotowa",
    "Mysz Nested Desktop nad grą", "Przywraca kursor i kliknięcie prawego gładzika w Nested Desktop, gdy działa inna aplikacja w trybie gry",
    "Bezwładność gładzika", "Kontynuuje ruch kursora i przewijanie po szybkim przesunięciu; wyłącz, aby zatrzymać ruch natychmiast po puszczeniu gładzika",
    "Poprawka wskaźnika RustDesk", "Zapobiega podwójnym kursorom i przeskakiwaniu wskaźnika w Nested Desktop; Dodaj / Napraw RustDesk automatycznie instaluje wymaganą integrację systemową",
  ]),
  portuguese: define([
    "Ferramentas do sistema", "Instale e faça a gestão de correções específicas do sistema", "Estado", "A carregar…",
    "Correção do MangoHud para Nested Desktop", "Impede que processos protegidos do Nested Desktop terminem o MangoApp e ocultem a sobreposição de desempenho",
    "Instalada", "É necessário atualizar ou reparar", "Não instalada", "Indisponível neste sistema",
    "Instalar / Reparar", "Remover correção", "Correção do MangoHud instalada", "Correção do MangoHud removida",
    "SteamOS no Modo de Jogo", "Adiciona ou repara um atalho do Nested Desktop totalmente configurado na biblioteca Steam",
    "Adicionar / Reparar SteamOS", "A aplicação SteamOS está pronta",
    "Rato do Nested Desktop sobre jogos", "Restaura o cursor e o clique do trackpad direito no Nested Desktop enquanto outra aplicação do Modo de Jogo está em execução",
    "Inércia do trackpad", "Mantém o movimento do cursor e do deslocamento após um gesto rápido; desative para parar imediatamente ao soltar o trackpad",
    "Correção do ponteiro do RustDesk", "Evita cursores duplicados e saltos do ponteiro no Nested Desktop; Adicionar / Reparar RustDesk instala automaticamente a integração de sistema necessária",
  ]),
  romanian: define([
    "Instrumente de sistem", "Instalează și gestionează remedieri de sistem punctuale", "Stare", "Se încarcă…",
    "Remediere MangoHud pentru Nested Desktop", "Împiedică procesele protejate Nested Desktop să oprească MangoApp și să ascundă suprapunerea de performanță",
    "Instalată", "Este necesară actualizarea sau repararea", "Neinstalată", "Indisponibilă pe acest sistem",
    "Instalează / Repară", "Elimină remedierea", "Remedierea MangoHud a fost instalată", "Remedierea MangoHud a fost eliminată",
    "SteamOS în modul Joc", "Adaugă sau repară o scurtătură Nested Desktop complet configurată în biblioteca Steam",
    "Adaugă / Repară SteamOS", "Aplicația SteamOS este pregătită",
    "Mouse Nested Desktop peste joc", "Restabilește cursorul și clicul trackpadului drept în Nested Desktop când rulează o altă aplicație în modul Joc",
    "Inerția trackpadului", "Continuă mișcarea cursorului și derularea după o glisare rapidă; dezactivează pentru oprire imediată la eliberarea trackpadului",
    "Remediere indicator RustDesk", "Previne cursoarele duplicate și salturile indicatorului în Nested Desktop; Adaugă / Repară RustDesk instalează automat integrarea de sistem necesară",
  ]),
  russian: define([
    "Системные инструменты", "Установка и управление точечными системными исправлениями", "Состояние", "Загрузка…",
    "Исправление MangoHud для Nested Desktop", "Не даёт защищённым процессам Nested Desktop аварийно завершать MangoApp и скрывать оверлей производительности",
    "Установлено", "Требуется обновление или восстановление", "Не установлено", "Недоступно в этой системе",
    "Установить / Исправить", "Удалить исправление", "Исправление MangoHud установлено", "Исправление MangoHud удалено",
    "SteamOS в игровом режиме", "Добавляет или исправляет полностью настроенный ярлык Nested Desktop в библиотеке Steam",
    "Добавить / Исправить SteamOS", "Приложение SteamOS готово",
    "Мышь Nested Desktop поверх игры", "Восстанавливает курсор и клик правого трекпада в Nested Desktop, когда параллельно запущено другое приложение в игровом режиме",
    "Инерция трекпадов", "Продолжает движение курсора и прокрутки после быстрого свайпа; отключите для мгновенной остановки при отпускании трекпада",
    "Исправление курсора RustDesk", "Убирает второй курсор и телепортацию указателя в Nested Desktop; «Добавить / исправить RustDesk» автоматически устанавливает нужную системную интеграцию",
  ]),
  schinese: define([
    "系统工具", "安装和管理范围明确的系统修复", "状态", "正在加载…",
    "MangoHud Nested Desktop 修复", "防止受保护的 Nested Desktop 进程导致 MangoApp 崩溃并隐藏性能叠加层",
    "已安装", "需要更新或修复", "未安装", "此系统不可用",
    "安装 / 修复", "移除修复", "MangoHud 修复已安装", "MangoHud 修复已移除",
    "游戏模式中的 SteamOS", "在 Steam 库中添加或修复已完整配置的 Nested Desktop 快捷方式",
    "添加 / 修复 SteamOS", "SteamOS 应用已准备就绪",
    "游戏上方的 Nested Desktop 鼠标", "当另一个游戏模式应用正在运行时，恢复 Nested Desktop 中的右触控板光标和点击",
    "触控板惯性", "快速滑动后继续移动光标和滚动；关闭后松开触控板会立即停止",
    "RustDesk 指针修复", "防止 Nested Desktop 中出现重复光标和指针跳跃；“添加 / 修复 RustDesk”会自动安装所需的系统集成",
  ]),
  spanish: define([
    "Herramientas del sistema", "Instala y administra correcciones específicas del sistema", "Estado", "Cargando…",
    "Corrección de MangoHud para Nested Desktop", "Evita que los procesos protegidos de Nested Desktop cierren MangoApp y oculten la superposición de rendimiento",
    "Instalada", "Se requiere actualizar o reparar", "No instalada", "No disponible en este sistema",
    "Instalar / Reparar", "Eliminar corrección", "Corrección de MangoHud instalada", "Corrección de MangoHud eliminada",
    "SteamOS en modo juego", "Añade o repara un acceso directo de Nested Desktop totalmente configurado en la biblioteca de Steam",
    "Añadir / Reparar SteamOS", "La aplicación SteamOS está lista",
    "Ratón de Nested Desktop sobre juegos", "Restaura el cursor y el clic del trackpad derecho en Nested Desktop mientras se ejecuta otra aplicación del modo Juego",
    "Inercia del trackpad", "Continúa el movimiento del cursor y el desplazamiento tras un gesto rápido; desactívala para detenerlos al soltar el trackpad",
    "Corrección del puntero de RustDesk", "Evita cursores duplicados y saltos del puntero en Nested Desktop; Añadir / Reparar RustDesk instala automáticamente la integración del sistema necesaria",
  ]),
  swedish: define([
    "Systemverktyg", "Installera och hantera riktade systemkorrigeringar", "Status", "Läser in…",
    "MangoHud-korrigering för Nested Desktop", "Förhindrar skyddade Nested Desktop-processer från att krascha MangoApp och dölja prestandaöverlägget",
    "Installerad", "Uppdatering eller reparation krävs", "Inte installerad", "Inte tillgänglig på detta system",
    "Installera / Reparera", "Ta bort korrigering", "MangoHud-korrigeringen är installerad", "MangoHud-korrigeringen är borttagen",
    "SteamOS i spelläge", "Lägger till eller reparerar en fullständigt konfigurerad Nested Desktop-genväg i Steam-biblioteket",
    "Lägg till / Reparera SteamOS", "SteamOS-programmet är klart",
    "Nested Desktop-mus över spel", "Återställer markören och klick med höger styrplatta i Nested Desktop medan en annan spellägesapp körs",
    "Styrplattans tröghet", "Fortsätter markör- och rullrörelsen efter ett snabbt svep; inaktivera för att stanna direkt när styrplattan släpps",
    "RustDesk-pekarkorrigering", "Förhindrar dubbla markörer och pekarhopp i Nested Desktop; Lägg till / Reparera RustDesk installerar automatiskt den systemintegration som krävs",
  ]),
  tchinese: define([
    "系統工具", "安裝及管理範圍明確的系統修正", "狀態", "載入中…",
    "MangoHud Nested Desktop 修正", "防止受保護的 Nested Desktop 程序造成 MangoApp 當機並隱藏效能重疊顯示",
    "已安裝", "需要更新或修復", "未安裝", "此系統無法使用",
    "安裝 / 修復", "移除修正", "MangoHud 修正已安裝", "MangoHud 修正已移除",
    "遊戲模式中的 SteamOS", "在 Steam 收藏庫中新增或修復已完整設定的 Nested Desktop 捷徑",
    "新增 / 修復 SteamOS", "SteamOS 應用程式已準備就緒",
    "遊戲上方的 Nested Desktop 滑鼠", "當另一個遊戲模式應用程式正在執行時，恢復 Nested Desktop 中的右觸控板游標與點擊",
    "觸控板慣性", "快速滑動後繼續移動游標與捲動；關閉後放開觸控板便會立即停止",
    "RustDesk 指標修正", "防止 Nested Desktop 中出現重複游標與指標跳動；「新增 / 修復 RustDesk」會自動安裝所需的系統整合",
  ]),
  thai: define([
    "เครื่องมือระบบ", "ติดตั้งและจัดการการแก้ไขระบบแบบเฉพาะจุด", "สถานะ", "กำลังโหลด…",
    "การแก้ไข MangoHud สำหรับ Nested Desktop", "ป้องกันโพรเซส Nested Desktop ที่ได้รับการป้องกันไม่ให้ทำให้ MangoApp หยุดทำงานและซ่อนโอเวอร์เลย์ประสิทธิภาพ",
    "ติดตั้งแล้ว", "ต้องอัปเดตหรือซ่อมแซม", "ยังไม่ได้ติดตั้ง", "ใช้ไม่ได้ในระบบนี้",
    "ติดตั้ง / ซ่อมแซม", "นำการแก้ไขออก", "ติดตั้งการแก้ไข MangoHud แล้ว", "นำการแก้ไข MangoHud ออกแล้ว",
    "SteamOS ในโหมดเกม", "เพิ่มหรือซ่อมแซมทางลัด Nested Desktop ที่กำหนดค่าไว้อย่างสมบูรณ์ในคลัง Steam",
    "เพิ่ม / ซ่อมแซม SteamOS", "แอปพลิเคชัน SteamOS พร้อมแล้ว",
    "เมาส์ Nested Desktop เหนือเกม", "คืนค่าเคอร์เซอร์และการคลิกด้วยแทร็กแพดขวาใน Nested Desktop ขณะที่แอปโหมดเกมอื่นกำลังทำงาน",
    "แรงเฉื่อยของแทร็กแพด", "เลื่อนเคอร์เซอร์และการเลื่อนหน้าจอต่อหลังปัดเร็ว ปิดเพื่อหยุดทันทีเมื่อปล่อยแทร็กแพด",
    "การแก้ไขตัวชี้ RustDesk", "ป้องกันเคอร์เซอร์ซ้ำและตัวชี้กระโดดใน Nested Desktop; เพิ่ม / ซ่อมแซม RustDesk จะติดตั้งการเชื่อมต่อระบบที่จำเป็นโดยอัตโนมัติ",
  ]),
  turkish: define([
    "Sistem araçları", "Hedefli sistem düzeltmelerini kurun ve yönetin", "Durum", "Yükleniyor…",
    "Nested Desktop için MangoHud düzeltmesi", "Korunan Nested Desktop işlemlerinin MangoApp’i çökertmesini ve performans katmanını gizlemesini önler",
    "Kurulu", "Güncelleme veya onarım gerekli", "Kurulu değil", "Bu sistemde kullanılamıyor",
    "Kur / Onar", "Düzeltmeyi kaldır", "MangoHud düzeltmesi kuruldu", "MangoHud düzeltmesi kaldırıldı",
    "Oyun Modunda SteamOS", "Steam kütüphanesine tamamen yapılandırılmış bir Nested Desktop kısayolu ekler veya onarır",
    "SteamOS Ekle / Onar", "SteamOS uygulaması hazır",
    "Oyun üzerinde Nested Desktop faresi", "Başka bir Oyun Modu uygulaması çalışırken Nested Desktop’ta sağ izleme dörtgeni imlecini ve tıklamayı geri getirir",
    "İzleme dörtgeni ataleti", "Hızlı kaydırmadan sonra imleç ve kaydırma hareketini sürdürür; izleme dörtgeni bırakıldığında hemen durması için kapatın",
    "RustDesk işaretçi düzeltmesi", "Nested Desktop’ta çift imleci ve işaretçi sıçramalarını önler; RustDesk Ekle / Onar gerekli sistem entegrasyonunu otomatik olarak kurar",
  ]),
  ukrainian: define([
    "Системні інструменти", "Встановлення й керування точковими системними виправленнями", "Стан", "Завантаження…",
    "Виправлення MangoHud для Nested Desktop", "Не дає захищеним процесам Nested Desktop аварійно завершувати MangoApp і приховувати оверлей продуктивності",
    "Встановлено", "Потрібне оновлення або відновлення", "Не встановлено", "Недоступно в цій системі",
    "Встановити / Виправити", "Видалити виправлення", "Виправлення MangoHud встановлено", "Виправлення MangoHud видалено",
    "SteamOS в ігровому режимі", "Додає або виправляє повністю налаштований ярлик Nested Desktop у бібліотеці Steam",
    "Додати / Виправити SteamOS", "Застосунок SteamOS готовий",
    "Миша Nested Desktop поверх гри", "Відновлює курсор і натискання правого трекпада в Nested Desktop, коли паралельно запущено іншу програму в ігровому режимі",
    "Інерція трекпада", "Продовжує рух курсора та прокручування після швидкого свайпа; вимкніть для миттєвої зупинки після відпускання трекпада",
    "Виправлення вказівника RustDesk", "Запобігає подвійному курсору та стрибкам вказівника в Nested Desktop; «Додати / Виправити RustDesk» автоматично встановлює потрібну системну інтеграцію",
  ]),
  vietnamese: define([
    "Công cụ hệ thống", "Cài đặt và quản lý các bản sửa lỗi hệ thống có phạm vi rõ ràng", "Trạng thái", "Đang tải…",
    "Bản sửa MangoHud cho Nested Desktop", "Ngăn các tiến trình Nested Desktop được bảo vệ làm sập MangoApp và ẩn lớp phủ hiệu năng",
    "Đã cài đặt", "Cần cập nhật hoặc sửa chữa", "Chưa cài đặt", "Không khả dụng trên hệ thống này",
    "Cài đặt / Sửa chữa", "Gỡ bản sửa", "Đã cài bản sửa MangoHud", "Đã gỡ bản sửa MangoHud",
    "SteamOS trong Chế độ trò chơi", "Thêm hoặc sửa lối tắt Nested Desktop đã được cấu hình đầy đủ trong thư viện Steam",
    "Thêm / Sửa SteamOS", "Ứng dụng SteamOS đã sẵn sàng",
    "Chuột Nested Desktop trên trò chơi", "Khôi phục con trỏ và thao tác nhấp của bàn di chuột phải trong Nested Desktop khi một ứng dụng Chế độ trò chơi khác đang chạy",
    "Quán tính bàn di chuột", "Tiếp tục di chuyển con trỏ và cuộn sau cú vuốt nhanh; tắt để dừng ngay khi nhả bàn di chuột",
    "Bản sửa con trỏ RustDesk", "Ngăn con trỏ trùng lặp và nhảy vị trí trong Nested Desktop; Thêm / Sửa RustDesk tự động cài đặt tích hợp hệ thống cần thiết",
  ]),
};

type RustDeskOptionsTranslation = Pick<
  SystemToolsTranslation,
  | "rustDeskFocusOnInput"
  | "rustDeskFocusOnInputDescription"
  | "rustDeskScrollInertia"
  | "rustDeskScrollInertiaDescription"
>;

const rustDeskOptionsTranslations:
Record<string, RustDeskOptionsTranslation> = {
  arabic: {
    rustDeskFocusOnInput: "الانتقال إلى Nested Desktop عند إدخال RustDesk",
    rustDeskFocusOnInputDescription: "⚠ يجلب Nested Desktop إلى المقدمة عند إدخال RustDesk. يتجاوز ذلك شاشة قفل Steam التي تطلب رمز PIN. معطّل افتراضيًا؛ تفعيله يعني قبولك لهذه المخاطرة",
    rustDeskScrollInertia: "قصور عجلة RustDesk",
    rustDeskScrollInertiaDescription: "يضيف انزلاقًا طبيعيًا قصيرًا بعد تدوير العجلة بسرعة؛ يكون معطّلًا افتراضيًا ولا يؤثر في قصور لوحة التتبع",
  },
  brazilian: {
    rustDeskFocusOnInput: "Focar o Nested Desktop com entrada do RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Traz o Nested Desktop para a frente com a entrada do RustDesk. Isso ignora a tela de bloqueio do Steam com PIN. Desativado por padrão; ao ativar, você aceita esse risco",
    rustDeskScrollInertia: "Inércia da roda do RustDesk",
    rustDeskScrollInertiaDescription: "Adiciona um deslizamento natural curto após rolar rapidamente; vem desativada e não afeta a inércia dos trackpads",
  },
  bulgarian: {
    rustDeskFocusOnInput: "Фокус върху Nested Desktop при вход от RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Извежда Nested Desktop на преден план при вход от RustDesk. Това заобикаля заключващия екран на Steam с PIN. Изключено по подразбиране; с включването приемате този риск",
    rustDeskScrollInertia: "Инерция на колелцето в RustDesk",
    rustDeskScrollInertiaDescription: "Добавя кратко естествено довършване след бързо превъртане; изключено е по подразбиране и не влияе на инерцията на тракпадите",
  },
  czech: {
    rustDeskFocusOnInput: "Zaměřit Nested Desktop při vstupu z RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Přenese Nested Desktop do popředí při vstupu z RustDesk. Tím se obejde zamykací obrazovka Steamu s PINem. Ve výchozím stavu vypnuto; zapnutím přijímáte toto riziko",
    rustDeskScrollInertia: "Setrvačnost kolečka RustDesk",
    rustDeskScrollInertiaDescription: "Po rychlém rolování přidá krátký přirozený dojezd; ve výchozím stavu je vypnutá a neovlivňuje setrvačnost trackpadů",
  },
  danish: {
    rustDeskFocusOnInput: "Fokusér Nested Desktop ved RustDesk-input",
    rustDeskFocusOnInputDescription: "⚠ Bringer Nested Desktop frem ved RustDesk-input. Dette omgår Steams PIN-låseskærm. Slået fra som standard; ved at aktivere accepterer du denne risiko",
    rustDeskScrollInertia: "RustDesk-musehjulsinerti",
    rustDeskScrollInertiaDescription: "Tilføjer et kort naturligt efterløb efter hurtig rulning; er slået fra som standard og påvirker ikke trackpad-inerti",
  },
  dutch: {
    rustDeskFocusOnInput: "Nested Desktop focussen bij RustDesk-invoer",
    rustDeskFocusOnInputDescription: "⚠ Brengt Nested Desktop naar de voorgrond bij RustDesk-invoer. Dit omzeilt het Steam-vergrendelscherm met pincode. Standaard uit; door dit in te schakelen accepteer je dit risico",
    rustDeskScrollInertia: "RustDesk-wieltraagheid",
    rustDeskScrollInertiaDescription: "Voegt een korte natuurlijke uitloop toe na snel scrollen; staat standaard uit en beïnvloedt de trackpadtraagheid niet",
  },
  finnish: {
    rustDeskFocusOnInput: "Kohdista Nested Desktop RustDesk-syötteellä",
    rustDeskFocusOnInputDescription: "⚠ Tuo Nested Desktopin etualalle RustDesk-syötteellä. Tämä ohittaa Steamin PIN-lukitusnäytön. Oletuksena pois käytöstä; ottamalla käyttöön hyväksyt tämän riskin",
    rustDeskScrollInertia: "RustDesk-rullan vieritysinertia",
    rustDeskScrollInertiaDescription: "Lisää lyhyen luonnollisen jälkiliikkeen nopean vierityksen jälkeen; oletuksena pois käytöstä eikä vaikuta ohjauslevyjen inertiaan",
  },
  french: {
    rustDeskFocusOnInput: "Activer Nested Desktop lors d’une entrée RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Place Nested Desktop au premier plan lors d’une entrée RustDesk. Cela contourne l’écran de verrouillage Steam avec code PIN. Désactivé par défaut ; l’activer signifie accepter ce risque",
    rustDeskScrollInertia: "Inertie de la molette RustDesk",
    rustDeskScrollInertiaDescription: "Ajoute une courte glisse naturelle après un défilement rapide ; désactivée par défaut et sans effet sur l’inertie des trackpads",
  },
  german: {
    rustDeskFocusOnInput: "Nested Desktop bei RustDesk-Eingabe fokussieren",
    rustDeskFocusOnInputDescription: "⚠ Holt Nested Desktop bei RustDesk-Eingaben in den Vordergrund. Dies umgeht den Steam-PIN-Sperrbildschirm. Standardmäßig deaktiviert; mit dem Aktivieren akzeptierst du dieses Risiko",
    rustDeskScrollInertia: "RustDesk-Mausradträgheit",
    rustDeskScrollInertiaDescription: "Fügt nach schnellem Scrollen einen kurzen natürlichen Nachlauf hinzu; standardmäßig deaktiviert und unabhängig von der Trackpad-Trägheit",
  },
  greek: {
    rustDeskFocusOnInput: "Εστίαση Nested Desktop με είσοδο RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Φέρνει το Nested Desktop στο προσκήνιο με είσοδο RustDesk. Αυτό παρακάμπτει την οθόνη κλειδώματος PIN του Steam. Ανενεργό από προεπιλογή· ενεργοποιώντας το αποδέχεστε αυτόν τον κίνδυνο",
    rustDeskScrollInertia: "Αδράνεια τροχού RustDesk",
    rustDeskScrollInertiaDescription: "Προσθέτει μια σύντομη φυσική κύλιση μετά από γρήγορη χρήση του τροχού· είναι απενεργοποιημένη από προεπιλογή και δεν επηρεάζει την αδράνεια των trackpad",
  },
  hungarian: {
    rustDeskFocusOnInput: "Nested Desktop fókusza RustDesk-bevitelkor",
    rustDeskFocusOnInputDescription: "⚠ RustDesk-bevitelkor előtérbe hozza a Nested Desktopot. Ez megkerüli a Steam PIN-kódos zárolási képernyőjét. Alapértelmezetten kikapcsolva; bekapcsolásával elfogadod ezt a kockázatot",
    rustDeskScrollInertia: "RustDesk-görgő tehetetlensége",
    rustDeskScrollInertiaDescription: "Rövid természetes továbbgördülést ad a gyors görgetéshez; alapértelmezetten ki van kapcsolva, és nem befolyásolja az érintőpad tehetetlenségét",
  },
  indonesian: {
    rustDeskFocusOnInput: "Fokuskan Nested Desktop saat ada input RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Membawa Nested Desktop ke depan saat ada input RustDesk. Ini melewati layar kunci PIN Steam. Nonaktif secara bawaan; dengan mengaktifkannya Anda menerima risiko ini",
    rustDeskScrollInertia: "Inersia roda RustDesk",
    rustDeskScrollInertiaDescription: "Menambahkan luncuran alami singkat setelah menggulir cepat; nonaktif secara bawaan dan tidak memengaruhi inersia trackpad",
  },
  italian: {
    rustDeskFocusOnInput: "Attiva Nested Desktop con l’input RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Porta Nested Desktop in primo piano con l’input RustDesk. Questo aggira la schermata di blocco PIN di Steam. Disattivato per impostazione predefinita; attivandolo accetti questo rischio",
    rustDeskScrollInertia: "Inerzia della rotellina RustDesk",
    rustDeskScrollInertiaDescription: "Aggiunge un breve scorrimento naturale dopo una rotazione rapida; disattivata per impostazione predefinita e indipendente dall’inerzia dei trackpad",
  },
  japanese: {
    rustDeskFocusOnInput: "RustDesk 入力で Nested Desktop に切り替える",
    rustDeskFocusOnInputDescription: "⚠ RustDesk のポインターまたはキーボード入力で Nested Desktop を前面に表示します。Steam の PIN ロック画面を回避します。既定では無効です。有効にすると、このリスクを承認したものとみなされます",
    rustDeskScrollInertia: "RustDesk ホイールの慣性",
    rustDeskScrollInertiaDescription: "ホイールを素早く回した後に短く自然な余韻を加えます。既定では無効で、トラックパッドの慣性には影響しません",
  },
  koreana: {
    rustDeskFocusOnInput: "RustDesk 입력 시 Nested Desktop 전환",
    rustDeskFocusOnInputDescription: "⚠ RustDesk 포인터 또는 키보드 입력 시 Nested Desktop을 앞으로 가져옵니다. Steam PIN 잠금 화면을 우회합니다. 기본값은 꺼짐이며, 활성화하면 이 위험에 동의하는 것입니다",
    rustDeskScrollInertia: "RustDesk 휠 관성",
    rustDeskScrollInertiaDescription: "휠을 빠르게 스크롤한 뒤 짧고 자연스럽게 이어집니다. 기본값은 꺼짐이며 트랙패드 관성에는 영향을 주지 않습니다",
  },
  latam: {
    rustDeskFocusOnInput: "Enfocar Nested Desktop con la entrada de RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Pone Nested Desktop en primer plano con la entrada de RustDesk. Esto omite la pantalla de bloqueo de Steam con PIN. Desactivado de forma predeterminada; al activarlo aceptas este riesgo",
    rustDeskScrollInertia: "Inercia de la rueda de RustDesk",
    rustDeskScrollInertiaDescription: "Añade un breve deslizamiento natural después de desplazar rápidamente; está desactivada de forma predeterminada y no afecta la inercia de los trackpads",
  },
  malay: {
    rustDeskFocusOnInput: "Fokus Nested Desktop apabila ada input RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Membawa Nested Desktop ke hadapan apabila ada input RustDesk. Ini memintas skrin kunci PIN Steam. Dimatikan secara lalai; dengan mengaktifkannya anda menerima risiko ini",
    rustDeskScrollInertia: "Inersia roda RustDesk",
    rustDeskScrollInertiaDescription: "Menambah luncuran semula jadi yang singkat selepas tatal pantas; dimatikan secara lalai dan tidak menjejaskan inersia pad jejak",
  },
  norwegian: {
    rustDeskFocusOnInput: "Fokuser Nested Desktop ved RustDesk-inndata",
    rustDeskFocusOnInputDescription: "⚠ Henter Nested Desktop frem ved RustDesk-inndata. Dette omgår Steams PIN-låseskjerm. Av som standard; ved å aktivere godtar du denne risikoen",
    rustDeskScrollInertia: "RustDesk-rullehjulsinerti",
    rustDeskScrollInertiaDescription: "Legger til en kort naturlig etterrulling etter rask rulling; er av som standard og påvirker ikke styreplateinerti",
  },
  polish: {
    rustDeskFocusOnInput: "Aktywuj Nested Desktop przy wejściu RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Przenosi Nested Desktop na pierwszy plan przy wejściu RustDesk. Omija to ekran blokady Steam z kodem PIN. Domyślnie wyłączone; włączając, akceptujesz to ryzyko",
    rustDeskScrollInertia: "Bezwładność kółka RustDesk",
    rustDeskScrollInertiaDescription: "Dodaje krótki naturalny wybieg po szybkim przewijaniu; domyślnie wyłączona i niezależna od bezwładności gładzików",
  },
  portuguese: {
    rustDeskFocusOnInput: "Focar o Nested Desktop com entrada do RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Traz o Nested Desktop para a frente com entrada do RustDesk. Isto ignora o ecrã de bloqueio do Steam com PIN. Desativado por predefinição; ao ativar, aceita este risco",
    rustDeskScrollInertia: "Inércia da roda do RustDesk",
    rustDeskScrollInertiaDescription: "Adiciona um curto deslizamento natural após deslocamento rápido; está desativada por predefinição e não afeta a inércia dos trackpads",
  },
  romanian: {
    rustDeskFocusOnInput: "Focalizează Nested Desktop la intrare RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Aduce Nested Desktop în prim-plan la intrare RustDesk. Aceasta ocolește ecranul de blocare Steam cu PIN. Dezactivat implicit; prin activare accepți acest risc",
    rustDeskScrollInertia: "Inerția rotiței RustDesk",
    rustDeskScrollInertiaDescription: "Adaugă o scurtă alunecare naturală după derularea rapidă; este dezactivată implicit și nu afectează inerția trackpadurilor",
  },
  russian: {
    rustDeskFocusOnInput: "Переключаться на ввод RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Выводит Nested Desktop на передний план при вводе мышью или клавиатурой через RustDesk. Функция обходит экран блокировки Steam с PIN-кодом. По умолчанию выключена; включая её, вы принимаете этот риск",
    rustDeskScrollInertia: "Инерция колеса RustDesk",
    rustDeskScrollInertiaDescription: "Добавляет короткое естественное докатывание после быстрой прокрутки; по умолчанию выключено и не влияет на инерцию трекпадов",
  },
  schinese: {
    rustDeskFocusOnInput: "收到 RustDesk 输入时切换到 Nested Desktop",
    rustDeskFocusOnInputDescription: "⚠ 收到 RustDesk 指针或键盘输入时将 Nested Desktop 切换到前台。这会绕过 Steam PIN 锁屏。默认关闭；启用即表示您接受此风险",
    rustDeskScrollInertia: "RustDesk 滚轮惯性",
    rustDeskScrollInertiaDescription: "快速滚动后增加短暂自然的惯性滑动；默认关闭，且不会影响触控板惯性",
  },
  spanish: {
    rustDeskFocusOnInput: "Enfocar Nested Desktop con la entrada de RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Pone Nested Desktop en primer plano con la entrada de RustDesk. Esto omite la pantalla de bloqueo de Steam con PIN. Desactivado de forma predeterminada; al activarlo aceptas este riesgo",
    rustDeskScrollInertia: "Inercia de la rueda de RustDesk",
    rustDeskScrollInertiaDescription: "Añade un breve deslizamiento natural tras desplazar rápidamente; está desactivada de forma predeterminada y no afecta a la inercia de los trackpads",
  },
  swedish: {
    rustDeskFocusOnInput: "Fokusera Nested Desktop vid RustDesk-inmatning",
    rustDeskFocusOnInputDescription: "⚠ Tar fram Nested Desktop vid RustDesk-inmatning. Detta kringgår Steams PIN-låsskärm. Avstängt som standard; genom att aktivera accepterar du denna risk",
    rustDeskScrollInertia: "RustDesk-rullhjulströghet",
    rustDeskScrollInertiaDescription: "Lägger till en kort naturlig efterrullning efter snabb rullning; är avstängd som standard och påverkar inte styrplattornas tröghet",
  },
  tchinese: {
    rustDeskFocusOnInput: "收到 RustDesk 輸入時切換至 Nested Desktop",
    rustDeskFocusOnInputDescription: "⚠ 收到 RustDesk 指標或鍵盤輸入時將 Nested Desktop 帶到前景。這會略過 Steam PIN 鎖定畫面。預設關閉；啟用即表示您接受此風險",
    rustDeskScrollInertia: "RustDesk 滾輪慣性",
    rustDeskScrollInertiaDescription: "快速捲動後加入短暫自然的慣性滑動；預設關閉，且不會影響觸控板慣性",
  },
  thai: {
    rustDeskFocusOnInput: "สลับไปยัง Nested Desktop เมื่อมีอินพุต RustDesk",
    rustDeskFocusOnInputDescription: "⚠ นำ Nested Desktop มาไว้ด้านหน้าเมื่อมีอินพุต RustDesk การทำเช่นนี้จะข้ามหน้าจอล็อก PIN ของ Steam ปิดไว้ตามค่าเริ่มต้น การเปิดใช้หมายถึงคุณยอมรับความเสี่ยงนี้",
    rustDeskScrollInertia: "แรงเฉื่อยล้อเลื่อน RustDesk",
    rustDeskScrollInertiaDescription: "เพิ่มการไหลต่ออย่างเป็นธรรมชาติช่วงสั้นหลังเลื่อนเร็ว ปิดไว้ตามค่าเริ่มต้นและไม่กระทบแรงเฉื่อยของแทร็กแพด",
  },
  turkish: {
    rustDeskFocusOnInput: "RustDesk girişinde Nested Desktop’a odaklan",
    rustDeskFocusOnInputDescription: "⚠ RustDesk girişi olduğunda Nested Desktop’ı öne getirir. Bu, Steam PIN kilit ekranını atlar. Varsayılan olarak kapalıdır; etkinleştirerek bu riski kabul edersiniz",
    rustDeskScrollInertia: "RustDesk tekerlek ataleti",
    rustDeskScrollInertiaDescription: "Hızlı kaydırmadan sonra kısa ve doğal bir devam hareketi ekler; varsayılan olarak kapalıdır ve izleme dörtgeni ataletini etkilemez",
  },
  ukrainian: {
    rustDeskFocusOnInput: "Фокусувати Nested Desktop при вводі RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Виводить Nested Desktop на передній план при введенні через RustDesk. Це обходить екран блокування Steam з PIN-кодом. Типово вимкнено; вмикаючи, ви приймаєте цей ризик",
    rustDeskScrollInertia: "Інерція колеса RustDesk",
    rustDeskScrollInertiaDescription: "Додає коротке природне докручування після швидкого прокручування; типово вимкнено й не впливає на інерцію трекпадів",
  },
  vietnamese: {
    rustDeskFocusOnInput: "Chuyển sang Nested Desktop khi có đầu vào RustDesk",
    rustDeskFocusOnInputDescription: "⚠ Đưa Nested Desktop lên trước khi có đầu vào RustDesk. Việc này bỏ qua màn hình khóa PIN của Steam. Mặc định tắt; khi bật, bạn chấp nhận rủi ro này",
    rustDeskScrollInertia: "Quán tính bánh xe RustDesk",
    rustDeskScrollInertiaDescription: "Thêm một đoạn trượt tự nhiên ngắn sau khi cuộn nhanh; mặc định tắt và không ảnh hưởng đến quán tính bàn di chuột",
  },
};

type ControllerOptionsTranslation = Pick<
  SystemToolsTranslation,
  | "controller"
  | "trackpadAutoRecovery"
  | "trackpadAutoRecoveryDescription"
>;

const controllerOptionsTranslations:
Record<string, ControllerOptionsTranslation> = {
  arabic: {
    controller: "وحدة التحكم",
    trackpadAutoRecovery: "الاسترداد التلقائي للوحة التتبع",
    trackpadAutoRecoveryDescription: "يكتشف السحب المقترن بنقرة فعلية ويعيد توصيل وحدة التحكم المدمجة لفترة وجيزة فقط بعد رفع اليد عن لوحتي التتبع؛ بحد أقصى مرة كل 30 ثانية",
  },
  brazilian: {
    controller: "Controle",
    trackpadAutoRecovery: "Recuperação automática do trackpad",
    trackpadAutoRecoveryDescription: "Detecta um gesto combinado com clique físico e reconecta brevemente o controle integrado somente após soltar os dois trackpads; limitado a uma vez a cada 30 segundos",
  },
  bulgarian: {
    controller: "Контролер",
    trackpadAutoRecovery: "Автоматично възстановяване на тракпада",
    trackpadAutoRecoveryDescription: "Разпознава плъзване с физическо щракване и за кратко свързва отново вградения контролер едва след отпускане на двата тракпада; най-много веднъж на 30 секунди",
  },
  czech: {
    controller: "Ovladač",
    trackpadAutoRecovery: "Automatické obnovení trackpadu",
    trackpadAutoRecoveryDescription: "Rozpozná přejetí spojené s fyzickým kliknutím a krátce znovu připojí vestavěný ovladač až po uvolnění obou trackpadů; nejvýše jednou za 30 sekund",
  },
  danish: {
    controller: "Controller",
    trackpadAutoRecovery: "Automatisk gendannelse af pegefelt",
    trackpadAutoRecoveryDescription: "Registrerer et strøg kombineret med et fysisk klik og genforbinder kortvarigt den indbyggede controller, når begge pegefelter er sluppet; højst én gang hvert 30. sekund",
  },
  dutch: {
    controller: "Controller",
    trackpadAutoRecovery: "Automatisch trackpadherstel",
    trackpadAutoRecoveryDescription: "Detecteert een veeg in combinatie met een fysieke klik en verbindt de ingebouwde controller pas kort opnieuw nadat beide trackpads zijn losgelaten; maximaal eenmaal per 30 seconden",
  },
  finnish: {
    controller: "Ohjain",
    trackpadAutoRecovery: "Ohjauslevyn automaattinen palautus",
    trackpadAutoRecoveryDescription: "Tunnistaa pyyhkäisyn ja fyysisen napsautuksen yhdistelmän sekä yhdistää sisäisen ohjaimen hetkeksi uudelleen vasta, kun molemmat ohjauslevyt on vapautettu; enintään kerran 30 sekunnissa",
  },
  french: {
    controller: "Manette",
    trackpadAutoRecovery: "Récupération automatique du pavé tactile",
    trackpadAutoRecoveryDescription: "Détecte un balayage combiné à un clic physique et reconnecte brièvement la manette intégrée uniquement après le relâchement des deux pavés tactiles ; au maximum une fois toutes les 30 secondes",
  },
  german: {
    controller: "Controller",
    trackpadAutoRecovery: "Automatische Trackpad-Wiederherstellung",
    trackpadAutoRecoveryDescription: "Erkennt ein Wischen mit physischem Klick und verbindet den integrierten Controller kurz neu, sobald beide Trackpads losgelassen wurden; höchstens einmal alle 30 Sekunden",
  },
  greek: {
    controller: "Χειριστήριο",
    trackpadAutoRecovery: "Αυτόματη επαναφορά trackpad",
    trackpadAutoRecoveryDescription: "Εντοπίζει σάρωση μαζί με φυσικό κλικ και επανασυνδέει για λίγο το ενσωματωμένο χειριστήριο μόνο αφού απελευθερωθούν και τα δύο trackpad· το πολύ μία φορά ανά 30 δευτερόλεπτα",
  },
  hungarian: {
    controller: "Vezérlő",
    trackpadAutoRecovery: "Érintőpad automatikus helyreállítása",
    trackpadAutoRecoveryDescription: "Észleli a fizikai kattintással egyidejű húzást, és csak mindkét érintőpad felengedése után csatlakoztatja röviden újra a beépített vezérlőt; legfeljebb 30 másodpercenként egyszer",
  },
  indonesian: {
    controller: "Kontroler",
    trackpadAutoRecovery: "Pemulihan trackpad otomatis",
    trackpadAutoRecoveryDescription: "Mendeteksi usapan yang disertai klik fisik dan menyambungkan ulang kontroler bawaan secara singkat hanya setelah kedua trackpad dilepas; paling sering sekali setiap 30 detik",
  },
  italian: {
    controller: "Controller",
    trackpadAutoRecovery: "Ripristino automatico del trackpad",
    trackpadAutoRecoveryDescription: "Rileva uno scorrimento combinato con un clic fisico e riconnette brevemente il controller integrato solo dopo il rilascio di entrambi i trackpad; al massimo una volta ogni 30 secondi",
  },
  japanese: {
    controller: "コントローラー",
    trackpadAutoRecovery: "トラックパッドの自動復旧",
    trackpadAutoRecoveryDescription: "スワイプと物理クリックの同時操作を検出し、両方のトラックパッドから指が離れた後に内蔵コントローラーを一時的に再接続します。実行は30秒に1回までです",
  },
  koreana: {
    controller: "컨트롤러",
    trackpadAutoRecovery: "트랙패드 자동 복구",
    trackpadAutoRecoveryDescription: "스와이프와 물리 클릭의 동시 입력을 감지하고 두 트랙패드에서 손을 뗀 뒤에만 내장 컨트롤러를 잠시 다시 연결합니다. 최대 30초에 한 번 실행됩니다",
  },
  latam: {
    controller: "Control",
    trackpadAutoRecovery: "Recuperación automática del trackpad",
    trackpadAutoRecoveryDescription: "Detecta un deslizamiento combinado con un clic físico y vuelve a conectar brevemente el control integrado solo después de soltar ambos trackpads; como máximo una vez cada 30 segundos",
  },
  malay: {
    controller: "Pengawal",
    trackpadAutoRecovery: "Pemulihan pad jejak automatik",
    trackpadAutoRecoveryDescription: "Mengesan leretan bersama klik fizikal dan menyambung semula pengawal terbina dalam buat seketika hanya selepas kedua-dua pad jejak dilepaskan; paling kerap sekali setiap 30 saat",
  },
  norwegian: {
    controller: "Kontroller",
    trackpadAutoRecovery: "Automatisk gjenoppretting av styreflate",
    trackpadAutoRecoveryDescription: "Oppdager et sveip kombinert med et fysisk klikk og kobler den innebygde kontrolleren kort til på nytt først når begge styreflatene er sluppet; høyst én gang hvert 30. sekund",
  },
  polish: {
    controller: "Kontroler",
    trackpadAutoRecovery: "Automatyczne odzyskiwanie gładzika",
    trackpadAutoRecoveryDescription: "Wykrywa przesunięcie połączone z fizycznym kliknięciem i na krótko ponownie podłącza wbudowany kontroler dopiero po zwolnieniu obu gładzików; najwyżej raz na 30 sekund",
  },
  portuguese: {
    controller: "Comando",
    trackpadAutoRecovery: "Recuperação automática do trackpad",
    trackpadAutoRecoveryDescription: "Deteta um gesto combinado com clique físico e volta a ligar brevemente o comando integrado apenas depois de largar os dois trackpads; no máximo uma vez a cada 30 segundos",
  },
  romanian: {
    controller: "Controler",
    trackpadAutoRecovery: "Recuperarea automată a trackpadului",
    trackpadAutoRecoveryDescription: "Detectează o glisare combinată cu un clic fizic și reconectează pentru scurt timp controlerul integrat numai după eliberarea ambelor trackpaduri; cel mult o dată la 30 de secunde",
  },
  russian: {
    controller: "Контроллер",
    trackpadAutoRecovery: "Автовосстановление трекпадов",
    trackpadAutoRecoveryDescription: "Определяет свайп с одновременным физическим кликом и кратко переподключает встроенный контроллер только после отпускания обоих трекпадов; не чаще одного раза в 30 секунд",
  },
  schinese: {
    controller: "控制器",
    trackpadAutoRecovery: "触控板自动恢复",
    trackpadAutoRecoveryDescription: "检测滑动与物理按压的组合操作，仅在双侧触控板均松开后短暂重连内置控制器；最多每30秒一次",
  },
  spanish: {
    controller: "Mando",
    trackpadAutoRecovery: "Recuperación automática del trackpad",
    trackpadAutoRecoveryDescription: "Detecta un deslizamiento combinado con un clic físico y vuelve a conectar brevemente el mando integrado solo después de soltar ambos trackpads; como máximo una vez cada 30 segundos",
  },
  swedish: {
    controller: "Handkontroll",
    trackpadAutoRecovery: "Automatisk återställning av styrplatta",
    trackpadAutoRecoveryDescription: "Upptäcker en svepning tillsammans med ett fysiskt klick och återansluter kort den inbyggda handkontrollen först när båda styrplattorna har släppts; högst en gång var 30:e sekund",
  },
  tchinese: {
    controller: "控制器",
    trackpadAutoRecovery: "觸控板自動復原",
    trackpadAutoRecoveryDescription: "偵測滑動與實體按壓的組合操作，僅在兩側觸控板皆放開後短暫重新連接內建控制器；最多每30秒一次",
  },
  thai: {
    controller: "คอนโทรลเลอร์",
    trackpadAutoRecovery: "การกู้คืนแทร็กแพดอัตโนมัติ",
    trackpadAutoRecoveryDescription: "ตรวจจับการปัดพร้อมการคลิกจริง และเชื่อมต่อคอนโทรลเลอร์ในตัวใหม่ชั่วครู่หลังปล่อยแทร็กแพดทั้งสองแล้วเท่านั้น โดยทำได้สูงสุดหนึ่งครั้งทุก 30 วินาที",
  },
  turkish: {
    controller: "Denetleyici",
    trackpadAutoRecovery: "Otomatik izleme dörtgeni kurtarma",
    trackpadAutoRecoveryDescription: "Fiziksel tıklamayla birlikte yapılan kaydırmayı algılar ve yalnızca iki izleme dörtgeni de bırakıldıktan sonra yerleşik denetleyiciyi kısa süreliğine yeniden bağlar; en fazla 30 saniyede bir",
  },
  ukrainian: {
    controller: "Контролер",
    trackpadAutoRecovery: "Автовідновлення трекпадів",
    trackpadAutoRecoveryDescription: "Виявляє свайп з одночасним фізичним натисканням і коротко перепідключає вбудований контролер лише після відпускання обох трекпадів; не частіше одного разу на 30 секунд",
  },
  vietnamese: {
    controller: "Tay cầm",
    trackpadAutoRecovery: "Tự động khôi phục bàn di chuột",
    trackpadAutoRecoveryDescription: "Phát hiện thao tác vuốt kết hợp với nhấn vật lý và chỉ kết nối lại nhanh bộ điều khiển tích hợp sau khi cả hai bàn di chuột được thả; tối đa một lần mỗi 30 giây",
  },
};

export const systemToolsTranslations:
Record<string, SystemToolsTranslation> = Object.fromEntries(
  Object.entries(baseSystemToolsTranslations).map(
    ([language, strings]) => [
      language,
      {
        ...strings,
        ...rustDeskOptionsTranslations[language],
        ...controllerOptionsTranslations[language],
      },
    ],
  ),
) as Record<string, SystemToolsTranslation>;
