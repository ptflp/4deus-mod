import type { SteamLanguage } from "./locales";

export interface CommonTranslation {
  pluginSettings: string;
  ok: string;
  menuButton: string;
}

type Values = [
  pluginSettings: string,
  ok: string,
  menuButton: string,
];

const define = ([
  pluginSettings,
]: Values): CommonTranslation => ({
  // These are fixed Steam hardware/UI labels, not natural-language prose.
  menuButton: "Menu",
  ok: "OK",
  pluginSettings,
});

export const commonTranslations:
Record<SteamLanguage, CommonTranslation> = {
  english: define([
    "Plugin settings",
    "OK",
    "Menu",
  ]),
  arabic: define([
    "إعدادات البرنامج المساعد",
    "حسنًا",
    "القائمة",
  ]),
  brazilian: define([
    "Configurações do plug-in",
    "OK",
    "Cardápio",
  ]),
  bulgarian: define([
    "Настройки на плъгина",
    "добре",
    "Меню",
  ]),
  czech: define([
    "Nastavení pluginu",
    "OK",
    "Menu",
  ]),
  danish: define([
    "Plugin-indstillinger",
    "OK",
    "Menu",
  ]),
  dutch: define([
    "Plugin-instellingen",
    "Oké",
    "Menukaart",
  ]),
  finnish: define([
    "Plugin asetukset",
    "OK",
    "Valikko",
  ]),
  french: define([
    "Paramètres du plugin",
    "D'accord",
    "Menus",
  ]),
  german: define([
    "Plugin-Einstellungen",
    "Okay",
    "Menü",
  ]),
  greek: define([
    "Ρυθμίσεις προσθηκών",
    "ΟΚ",
    "Μενού",
  ]),
  hungarian: define([
    "Plugin beállítások",
    "OK",
    "Menü",
  ]),
  indonesian: define([
    "Pengaturan plugin",
    "Oke",
    "Tidak bisa",
  ]),
  italian: define([
    "Impostazioni del plugin",
    "Va bene",
    "Menù",
  ]),
  japanese: define([
    "プラグイン設定",
    "OK",
    "メニュー",
  ]),
  koreana: define([
    "플러그인 설정",
    "알았어",
    "메뉴",
  ]),
  latam: define([
    "Configuración del complemento",
    "bien",
    "Menú",
  ]),
  malay: define([
    "Tetapan pemalam",
    "OK",
    "Menu",
  ]),
  norwegian: define([
    "Plugin-innstillinger",
    "OK",
    "Meny",
  ]),
  polish: define([
    "Ustawienia wtyczki",
    "OK",
    "Menu",
  ]),
  portuguese: define([
    "Configurações do plug-in",
    "OK",
    "Cardápio",
  ]),
  romanian: define([
    "Setări plugin",
    "OK",
    "Meniu",
  ]),
  russian: define([
    "Настройки плагина",
    "ОК",
    "Menu",
  ]),
  schinese: define([
    "插件设置",
    "好的",
    "菜单",
  ]),
  spanish: define([
    "Configuración del complemento",
    "bien",
    "Menú",
  ]),
  swedish: define([
    "Plugin-inställningar",
    "OK",
    "Meny",
  ]),
  tchinese: define([
    "插件設定",
    "好的",
    "選單",
  ]),
  thai: define([
    "การตั้งค่าปลั๊กอิน",
    "ตกลง",
    "เมนู",
  ]),
  turkish: define([
    "Eklenti ayarları",
    "tamam",
    "Menü",
  ]),
  ukrainian: define([
    "Налаштування плагіна",
    "добре",
    "Меню",
  ]),
  vietnamese: define([
    "Cài đặt plugin",
    "được rồi",
    "Thực đơn",
  ]),
};
