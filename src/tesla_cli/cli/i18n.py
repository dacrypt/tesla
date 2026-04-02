"""Internationalization — minimal i18n for tesla-cli.

Usage:
    from tesla_cli.cli.i18n import t
    console.print(t("order.watching", rn="RN123"))

Supported languages: en (default), es
Set via `tesla --lang es <command>` or TESLA_LANG env var.
"""

from __future__ import annotations

import os

# Global language, changed by --lang flag
_lang: str = os.environ.get("TESLA_LANG", "en").lower()


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang.lower()


def get_lang() -> str:
    return _lang


def t(key: str, **kwargs: str) -> str:
    """Return translated string for key. Falls back to English if not found."""
    strings = _STRINGS.get(_lang, _STRINGS["en"])
    text = strings.get(key) or _STRINGS["en"].get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


# ── String Catalog ───────────────────────────────────────────────────────────

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # order
        "order.no_rn": "No reservation number configured.\nRun: tesla config set reservation-number RNXXXXXXXXX",
        "order.watching": "Watching order {rn} (every {interval} min, Ctrl+C to stop)",
        "order.changes_at": "● Changes detected at {time}",
        "order.no_changes": "{time} No changes",
        "order.stopped": "Stopped watching.",
        "order.notif_failed": "Failed to send notification: {error}",
        # vehicle
        "vehicle.asleep_waking": "Vehicle asleep, waking up…",
        "vehicle.awake": "Vehicle is awake",
        "vehicle.wake_sent": "Wake command sent. Vehicle may take a moment to respond.",
        "vehicle.locked": "Vehicle locked",
        "vehicle.unlocked": "Vehicle unlocked",
        "vehicle.horn": "Horn honked",
        "vehicle.flash": "Lights flashed",
        "vehicle.sentry_on": "Sentry Mode enabled",
        "vehicle.sentry_off": "Sentry Mode disabled",
        "vehicle.sentry_unavailable": "Note: Sentry Mode not available (vehicle may not be parked)",
        "vehicle.trunk_opened": "{which} trunk opened",
        # charge
        "charge.started": "Charging started",
        "charge.stopped": "Charging stopped",
        "charge.limit_set": "Charge limit set to {limit}%",
        "charge.amps_set": "Charging amps set to {amps}A",
        # climate
        "climate.on": "Climate ON",
        "climate.off": "Climate OFF",
        "climate.temp_set": "Temperature set to {temp}°C",
        # dossier
        "dossier.not_found": "No dossier found. Run: tesla dossier build",
        "dossier.building": "Building dossier from all sources…",
        "dossier.diff_need_two": "Need at least 2 snapshots. Run: tesla dossier build",
        "dossier.diff_no_changes": "No differences found between the two snapshots.",
        "dossier.checklist_reset": "Checklist reset.",
        "dossier.checklist_complete": "All items checked! Enjoy your Tesla! ⚡",
        "dossier.checklist_hint": "Run: tesla dossier checklist --mark <N> to check item N",
        "dossier.gates_no_dossier": "No dossier found. Run: tesla dossier build for real data.",
        "dossier.delivery_set": "Delivery date set: {date}",
        # stream
        "stream.starting": "Starting live stream… press Ctrl+C to stop.",
        "stream.stopped": "Stream stopped.",
        "stream.asleep": "Vehicle is asleep (data from last known state)",
        # setup
        "setup.welcome": "Tesla CLI Setup Wizard",
        "setup.done": "Setup complete!",
        "setup.skip": "Already configured. Use --force to reconfigure.",
        # config
        "config.saved": "{key} = {value}",
        "config.unknown_key": "Unknown key: {key}",
        "config.alias_set": "Alias '{name}' -> {vin}",
        # teslaMate
        "teslaMate.not_configured": "TeslaMate not configured.\nRun: tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate",
        "teslaMate.connected": "Connected to TeslaMate ({url})",
        "teslaMate.no_trips": "No trips found in TeslaMate.",
        "teslaMate.no_charging": "No charging sessions found in TeslaMate.",
        "teslaMate.no_updates": "No OTA updates found in TeslaMate.",
        # errors
        "error.auth": "Not authenticated. Run: tesla config auth order",
        "error.no_vin": "No VIN configured. Run: tesla config set default-vin <VIN>",
        "error.token_expired": "Token expired. Run: tesla config auth order",
        "error.vehicle_not_found": "Vehicle {vin} not found on this account",
        "error.api": "API error {code}: {message}",
    },
    "es": {
        # orden
        "order.no_rn": "No hay número de reserva configurado.\nEjecuta: tesla config set reservation-number RNXXXXXXXXX",
        "order.watching": "Monitoreando orden {rn} (cada {interval} min, Ctrl+C para detener)",
        "order.changes_at": "● Cambios detectados a las {time}",
        "order.no_changes": "{time} Sin cambios",
        "order.stopped": "Monitoreo detenido.",
        "order.notif_failed": "Error al enviar notificación: {error}",
        # vehículo
        "vehicle.asleep_waking": "Vehículo dormido, activando…",
        "vehicle.awake": "Vehículo activo",
        "vehicle.wake_sent": "Comando de activación enviado. El vehículo puede tardar un momento.",
        "vehicle.locked": "Vehículo asegurado",
        "vehicle.unlocked": "Vehículo desbloqueado",
        "vehicle.horn": "Bocina activada",
        "vehicle.flash": "Luces destelladas",
        "vehicle.sentry_on": "Modo Centinela activado",
        "vehicle.sentry_off": "Modo Centinela desactivado",
        "vehicle.sentry_unavailable": "Nota: Modo Centinela no disponible (vehículo puede no estar estacionado)",
        "vehicle.trunk_opened": "{which} abierto",
        # carga
        "charge.started": "Carga iniciada",
        "charge.stopped": "Carga detenida",
        "charge.limit_set": "Límite de carga establecido en {limit}%",
        "charge.amps_set": "Amperios de carga establecidos en {amps}A",
        # clima
        "climate.on": "Clima ENCENDIDO",
        "climate.off": "Clima APAGADO",
        "climate.temp_set": "Temperatura establecida en {temp}°C",
        # dossier
        "dossier.not_found": "No se encontró el dossier. Ejecuta: tesla dossier build",
        "dossier.building": "Construyendo dossier desde todas las fuentes…",
        "dossier.diff_need_two": "Se necesitan al menos 2 instantáneas. Ejecuta: tesla dossier build",
        "dossier.diff_no_changes": "No se encontraron diferencias entre las dos instantáneas.",
        "dossier.checklist_reset": "Lista de verificación reiniciada.",
        "dossier.checklist_complete": "¡Todos los elementos verificados! ¡Disfruta tu Tesla! ⚡",
        "dossier.checklist_hint": "Ejecuta: tesla dossier checklist --mark <N> para marcar el elemento N",
        "dossier.gates_no_dossier": "No se encontró el dossier. Ejecuta: tesla dossier build para datos reales.",
        "dossier.delivery_set": "Fecha de entrega establecida: {date}",
        # stream
        "stream.starting": "Iniciando transmisión en vivo… presiona Ctrl+C para detener.",
        "stream.stopped": "Transmisión detenida.",
        "stream.asleep": "Vehículo dormido (datos del último estado conocido)",
        # configuración
        "config.saved": "{key} = {value}",
        "config.unknown_key": "Clave desconocida: {key}",
        "config.alias_set": "Alias '{name}' -> {vin}",
        # teslaMate
        "teslaMate.not_configured": "TeslaMate no configurado.\nEjecuta: tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate",
        "teslaMate.connected": "Conectado a TeslaMate ({url})",
        "teslaMate.no_trips": "No se encontraron viajes en TeslaMate.",
        "teslaMate.no_charging": "No se encontraron sesiones de carga en TeslaMate.",
        "teslaMate.no_updates": "No se encontró historial de actualizaciones en TeslaMate.",
        # errores
        "error.auth": "No autenticado. Ejecuta: tesla config auth order",
        "error.no_vin": "VIN no configurado. Ejecuta: tesla config set default-vin <VIN>",
        "error.token_expired": "Token expirado. Ejecuta: tesla config auth order",
        "error.vehicle_not_found": "Vehículo {vin} no encontrado en esta cuenta",
        "error.api": "Error de API {code}: {message}",
    },
    "pt": {
        # pedido
        "order.no_rn": "Número de reserva não configurado.\nExecute: tesla config set reservation-number RNXXXXXXXXX",
        "order.watching": "Monitorando pedido {rn} (a cada {interval} min, Ctrl+C para parar)",
        "order.changes_at": "● Alterações detectadas às {time}",
        "order.no_changes": "{time} Sem alterações",
        "order.stopped": "Monitoramento parado.",
        "order.notif_failed": "Falha ao enviar notificação: {error}",
        # veículo
        "vehicle.asleep_waking": "Veículo dormindo, acordando…",
        "vehicle.awake": "Veículo acordado",
        "vehicle.wake_sent": "Comando de ativação enviado. O veículo pode demorar um momento.",
        "vehicle.locked": "Veículo trancado",
        "vehicle.unlocked": "Veículo destrancado",
        "vehicle.horn": "Buzina ativada",
        "vehicle.flash": "Luzes piscadas",
        "vehicle.sentry_on": "Modo Sentinela ativado",
        "vehicle.sentry_off": "Modo Sentinela desativado",
        "vehicle.sentry_unavailable": "Nota: Modo Sentinela não disponível (veículo pode não estar estacionado)",
        "vehicle.trunk_opened": "{which} aberto",
        # carga
        "charge.started": "Carregamento iniciado",
        "charge.stopped": "Carregamento parado",
        "charge.limit_set": "Limite de carga definido em {limit}%",
        "charge.amps_set": "Amperes de carregamento definidos em {amps}A",
        # clima
        "climate.on": "Clima LIGADO",
        "climate.off": "Clima DESLIGADO",
        "climate.temp_set": "Temperatura definida em {temp}°C",
        # dossier
        "dossier.not_found": "Nenhum dossier encontrado. Execute: tesla dossier build",
        "dossier.building": "Construindo dossier de todas as fontes…",
        "dossier.diff_need_two": "São necessárias pelo menos 2 capturas. Execute: tesla dossier build",
        "dossier.diff_no_changes": "Nenhuma diferença encontrada entre as duas capturas.",
        "dossier.checklist_reset": "Lista de verificação reiniciada.",
        "dossier.checklist_complete": "Todos os itens verificados! Aproveite seu Tesla! ⚡",
        "dossier.checklist_hint": "Execute: tesla dossier checklist --mark <N> para marcar o item N",
        "dossier.gates_no_dossier": "Nenhum dossier encontrado. Execute: tesla dossier build para dados reais.",
        "dossier.delivery_set": "Data de entrega definida: {date}",
        # stream
        "stream.starting": "Iniciando transmissão ao vivo… pressione Ctrl+C para parar.",
        "stream.stopped": "Transmissão parada.",
        "stream.asleep": "Veículo dormindo (dados do último estado conhecido)",
        # configuração
        "config.saved": "{key} = {value}",
        "config.unknown_key": "Chave desconhecida: {key}",
        "config.alias_set": "Alias '{name}' -> {vin}",
        # teslaMate
        "teslaMate.not_configured": "TeslaMate não configurado.\nExecute: tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate",
        "teslaMate.connected": "Conectado ao TeslaMate ({url})",
        "teslaMate.no_trips": "Nenhuma viagem encontrada no TeslaMate.",
        "teslaMate.no_charging": "Nenhuma sessão de carregamento encontrada no TeslaMate.",
        "teslaMate.no_updates": "Nenhum histórico de atualizações encontrado no TeslaMate.",
        # erros
        "error.auth": "Não autenticado. Execute: tesla config auth order",
        "error.no_vin": "VIN não configurado. Execute: tesla config set default-vin <VIN>",
        "error.token_expired": "Token expirado. Execute: tesla config auth order",
        "error.vehicle_not_found": "Veículo {vin} não encontrado nesta conta",
        "error.api": "Erro de API {code}: {message}",
        # setup
        "setup.welcome": "Assistente de Configuração do Tesla CLI",
        "setup.done": "Configuração concluída!",
        "setup.skip": "Já configurado. Use --force para reconfigurar.",
    },
    "fr": {
        # commande
        "order.no_rn": "Numéro de réservation non configuré.\nExécutez : tesla config set reservation-number RNXXXXXXXXX",
        "order.watching": "Surveillance de la commande {rn} (toutes les {interval} min, Ctrl+C pour arrêter)",
        "order.changes_at": "● Modifications détectées à {time}",
        "order.no_changes": "{time} Aucune modification",
        "order.stopped": "Surveillance arrêtée.",
        "order.notif_failed": "Échec de l'envoi de la notification : {error}",
        # véhicule
        "vehicle.asleep_waking": "Véhicule en veille, réveil en cours…",
        "vehicle.awake": "Véhicule réveillé",
        "vehicle.wake_sent": "Commande de réveil envoyée. Le véhicule peut prendre un moment.",
        "vehicle.locked": "Véhicule verrouillé",
        "vehicle.unlocked": "Véhicule déverrouillé",
        "vehicle.horn": "Klaxon activé",
        "vehicle.flash": "Feux clignotés",
        "vehicle.sentry_on": "Mode Sentinelle activé",
        "vehicle.sentry_off": "Mode Sentinelle désactivé",
        "vehicle.sentry_unavailable": "Remarque : Mode Sentinelle indisponible (le véhicule n'est peut-être pas garé)",
        "vehicle.trunk_opened": "{which} ouvert",
        # charge
        "charge.started": "Charge démarrée",
        "charge.stopped": "Charge arrêtée",
        "charge.limit_set": "Limite de charge définie à {limit}%",
        "charge.amps_set": "Ampères de charge définis à {amps}A",
        # climatisation
        "climate.on": "Climatisation ACTIVÉE",
        "climate.off": "Climatisation DÉSACTIVÉE",
        "climate.temp_set": "Température réglée à {temp}°C",
        # dossier
        "dossier.not_found": "Aucun dossier trouvé. Exécutez : tesla dossier build",
        "dossier.building": "Construction du dossier depuis toutes les sources…",
        "dossier.diff_need_two": "Deux instantanés minimum requis. Exécutez : tesla dossier build",
        "dossier.diff_no_changes": "Aucune différence trouvée entre les deux instantanés.",
        "dossier.checklist_reset": "Liste de vérification réinitialisée.",
        "dossier.checklist_complete": "Tous les éléments vérifiés ! Profitez de votre Tesla ! ⚡",
        "dossier.checklist_hint": "Exécutez : tesla dossier checklist --mark <N> pour cocher l'élément N",
        "dossier.gates_no_dossier": "Aucun dossier trouvé. Exécutez : tesla dossier build pour les données réelles.",
        "dossier.delivery_set": "Date de livraison définie : {date}",
        # diffusion
        "stream.starting": "Démarrage de la diffusion en direct… appuyez sur Ctrl+C pour arrêter.",
        "stream.stopped": "Diffusion arrêtée.",
        "stream.asleep": "Véhicule en veille (données du dernier état connu)",
        # configuration
        "config.saved": "{key} = {value}",
        "config.unknown_key": "Clé inconnue : {key}",
        "config.alias_set": "Alias '{name}' -> {vin}",
        # teslaMate
        "teslaMate.not_configured": "TeslaMate non configuré.\nExécutez : tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate",
        "teslaMate.connected": "Connecté à TeslaMate ({url})",
        "teslaMate.no_trips": "Aucun trajet trouvé dans TeslaMate.",
        "teslaMate.no_charging": "Aucune session de charge trouvée dans TeslaMate.",
        "teslaMate.no_updates": "Aucun historique de mises à jour trouvé dans TeslaMate.",
        # erreurs
        "errors.vin_required": "VIN requis. Exécutez : tesla config set default-vin <VIN>",
        "errors.not_configured": "{feature} non configuré. Exécutez : tesla config set {key} <valeur>",
        "errors.backend_unavailable": "Backend {backend} indisponible : {reason}",
        "error.auth": "Non authentifié. Exécutez : tesla config auth order",
        "error.no_vin": "VIN non configuré. Exécutez : tesla config set default-vin <VIN>",
        "error.token_expired": "Token expiré. Exécutez : tesla config auth order",
        "error.vehicle_not_found": "Véhicule {vin} introuvable sur ce compte",
        "error.api": "Erreur API {code} : {message}",
        # configuration initiale
        "setup.welcome": "Bienvenue dans tesla-cli ! Configurons votre compte.",
        "setup.step": "Étape {n} / {total} — {label}",
        "setup.done": "Configuration terminée ! Exécutez tesla --help pour les commandes disponibles.",
        "setup.skip": "(ignoré)",
        "setup.found_order": "Commande trouvée : {model} — {status}",
        "setup.vin_not_assigned": "VIN pas encore attribué — uniquement le numéro de réservation enregistré.",
        "setup.multiple_orders": "Plusieurs commandes trouvées — choisissez-en une :",
    },
    "de": {
        # Bestellung
        "order.no_rn": "Keine Reservierungsnummer konfiguriert.\nAusführen: tesla config set reservation-number RNXXXXXXXXX",
        "order.watching": "Bestellung {rn} wird beobachtet (alle {interval} Min., Strg+C zum Stoppen)",
        "order.changes_at": "● Änderungen erkannt um {time}",
        "order.no_changes": "{time} Keine Änderungen",
        "order.stopped": "Beobachtung gestoppt.",
        "order.notif_failed": "Benachrichtigung fehlgeschlagen: {error}",
        # Fahrzeug
        "vehicle.asleep_waking": "Fahrzeug schläft, wird geweckt…",
        "vehicle.awake": "Fahrzeug ist wach",
        "vehicle.wake_sent": "Aufwachbefehl gesendet. Das Fahrzeug braucht einen Moment.",
        "vehicle.locked": "Fahrzeug gesperrt",
        "vehicle.unlocked": "Fahrzeug entsperrt",
        "vehicle.horn": "Hupe betätigt",
        "vehicle.flash": "Lichter geblinkt",
        "vehicle.sentry_on": "Sentinel-Modus aktiviert",
        "vehicle.sentry_off": "Sentinel-Modus deaktiviert",
        "vehicle.sentry_unavailable": "Hinweis: Sentinel-Modus nicht verfügbar (Fahrzeug möglicherweise nicht geparkt)",
        "vehicle.trunk_opened": "{which} geöffnet",
        # Laden
        "charge.started": "Laden gestartet",
        "charge.stopped": "Laden gestoppt",
        "charge.limit_set": "Ladelimit auf {limit}% gesetzt",
        "charge.amps_set": "Ladestrom auf {amps}A gesetzt",
        # Klimaanlage
        "climate.on": "Klimaanlage AN",
        "climate.off": "Klimaanlage AUS",
        "climate.temp_set": "Temperatur auf {temp}°C gesetzt",
        # Dossier
        "dossier.not_found": "Kein Dossier gefunden. Ausführen: tesla dossier build",
        "dossier.building": "Dossier wird aus allen Quellen erstellt…",
        "dossier.diff_need_two": "Mindestens 2 Schnappschüsse benötigt. Ausführen: tesla dossier build",
        "dossier.diff_no_changes": "Keine Unterschiede zwischen den beiden Schnappschüssen gefunden.",
        "dossier.checklist_reset": "Checkliste zurückgesetzt.",
        "dossier.checklist_complete": "Alle Punkte abgehakt! Viel Spaß mit Ihrem Tesla! ⚡",
        "dossier.checklist_hint": "Ausführen: tesla dossier checklist --mark <N> um Punkt N abzuhaken",
        "dossier.gates_no_dossier": "Kein Dossier gefunden. Ausführen: tesla dossier build für echte Daten.",
        "dossier.delivery_set": "Lieferdatum gesetzt: {date}",
        # Stream
        "stream.starting": "Live-Stream wird gestartet… Strg+C zum Stoppen.",
        "stream.stopped": "Stream gestoppt.",
        "stream.asleep": "Fahrzeug schläft (Daten aus letztem bekannten Zustand)",
        # Konfiguration
        "config.saved": "{key} = {value}",
        "config.unknown_key": "Unbekannter Schlüssel: {key}",
        "config.alias_set": "Alias '{name}' -> {vin}",
        # TeslaMate
        "teslaMate.not_configured": "TeslaMate nicht konfiguriert.\nAusführen: tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate",
        "teslaMate.connected": "Mit TeslaMate verbunden ({url})",
        "teslaMate.no_trips": "Keine Fahrten in TeslaMate gefunden.",
        "teslaMate.no_charging": "Keine Ladesitzungen in TeslaMate gefunden.",
        "teslaMate.no_updates": "Kein Update-Verlauf in TeslaMate gefunden.",
        # Fehler
        "errors.vin_required": "VIN erforderlich. Ausführen: tesla config set default-vin <VIN>",
        "errors.not_configured": "{feature} nicht konfiguriert. Ausführen: tesla config set {key} <wert>",
        "errors.backend_unavailable": "Backend {backend} nicht verfügbar: {reason}",
        "error.auth": "Nicht authentifiziert. Ausführen: tesla config auth order",
        "error.no_vin": "Keine VIN konfiguriert. Ausführen: tesla config set default-vin <VIN>",
        "error.token_expired": "Token abgelaufen. Ausführen: tesla config auth order",
        "error.vehicle_not_found": "Fahrzeug {vin} nicht in diesem Konto gefunden",
        "error.api": "API-Fehler {code}: {message}",
        # Einrichtung
        "setup.welcome": "Willkommen bei tesla-cli! Lassen Sie uns Ihr Konto einrichten.",
        "setup.step": "Schritt {n} / {total} — {label}",
        "setup.done": "Einrichtung abgeschlossen! Ausführen: tesla --help für verfügbare Befehle.",
        "setup.skip": "(übersprungen)",
        "setup.found_order": "Bestellung gefunden: {model} — {status}",
        "setup.vin_not_assigned": "VIN noch nicht zugewiesen — nur Reservierungsnummer gespeichert.",
        "setup.multiple_orders": "Mehrere Bestellungen gefunden — bitte eine auswählen:",
    },
    "it": {
        # Ordine
        "order.no_rn": "Numero di prenotazione non configurato.\nEseguire: tesla config set reservation-number RNXXXXXXXXX",
        "order.watching": "Monitoraggio ordine {rn} (ogni {interval} min, Ctrl+C per fermare)",
        "order.changes_at": "● Modifiche rilevate alle {time}",
        "order.no_changes": "{time} Nessuna modifica",
        "order.stopped": "Monitoraggio fermato.",
        "order.notif_failed": "Invio notifica fallito: {error}",
        # Veicolo
        "vehicle.asleep_waking": "Veicolo in standby, risveglio in corso…",
        "vehicle.awake": "Veicolo sveglio",
        "vehicle.wake_sent": "Comando di risveglio inviato. Il veicolo potrebbe impiegare un momento.",
        "vehicle.locked": "Veicolo bloccato",
        "vehicle.unlocked": "Veicolo sbloccato",
        "vehicle.horn": "Clacson attivato",
        "vehicle.flash": "Luci lampeggianti",
        "vehicle.sentry_on": "Modalità Sentinella attivata",
        "vehicle.sentry_off": "Modalità Sentinella disattivata",
        "vehicle.sentry_unavailable": "Nota: Modalità Sentinella non disponibile (il veicolo potrebbe non essere parcheggiato)",
        "vehicle.trunk_opened": "{which} aperto",
        # Ricarica
        "charge.started": "Ricarica avviata",
        "charge.stopped": "Ricarica fermata",
        "charge.limit_set": "Limite di ricarica impostato al {limit}%",
        "charge.amps_set": "Ampere di ricarica impostati a {amps}A",
        # Clima
        "climate.on": "Climatizzazione ACCESA",
        "climate.off": "Climatizzazione SPENTA",
        "climate.temp_set": "Temperatura impostata a {temp}°C",
        # Dossier
        "dossier.not_found": "Nessun dossier trovato. Eseguire: tesla dossier build",
        "dossier.building": "Costruzione dossier da tutte le fonti…",
        "dossier.diff_need_two": "Necessari almeno 2 snapshot. Eseguire: tesla dossier build",
        "dossier.diff_no_changes": "Nessuna differenza trovata tra i due snapshot.",
        "dossier.checklist_reset": "Lista di controllo reimpostata.",
        "dossier.checklist_complete": "Tutti gli elementi verificati! Godetevi la vostra Tesla! ⚡",
        "dossier.checklist_hint": "Eseguire: tesla dossier checklist --mark <N> per spuntare l'elemento N",
        "dossier.gates_no_dossier": "Nessun dossier trovato. Eseguire: tesla dossier build per dati reali.",
        "dossier.delivery_set": "Data di consegna impostata: {date}",
        # Streaming
        "stream.starting": "Avvio streaming in tempo reale… premere Ctrl+C per fermare.",
        "stream.stopped": "Streaming fermato.",
        "stream.asleep": "Veicolo in standby (dati dall'ultimo stato noto)",
        # Configurazione
        "config.saved": "{key} = {value}",
        "config.unknown_key": "Chiave sconosciuta: {key}",
        "config.alias_set": "Alias '{name}' -> {vin}",
        # TeslaMate
        "teslaMate.not_configured": "TeslaMate non configurato.\nEseguire: tesla teslaMate connect postgresql://user:pass@host:5432/teslaMate",
        "teslaMate.connected": "Connesso a TeslaMate ({url})",
        "teslaMate.no_trips": "Nessun viaggio trovato in TeslaMate.",
        "teslaMate.no_charging": "Nessuna sessione di ricarica trovata in TeslaMate.",
        "teslaMate.no_updates": "Nessuna cronologia aggiornamenti trovata in TeslaMate.",
        # Errori
        "errors.vin_required": "VIN richiesto. Eseguire: tesla config set default-vin <VIN>",
        "errors.not_configured": "{feature} non configurato. Eseguire: tesla config set {key} <valore>",
        "errors.backend_unavailable": "Backend {backend} non disponibile: {reason}",
        "error.auth": "Non autenticato. Eseguire: tesla config auth order",
        "error.no_vin": "VIN non configurato. Eseguire: tesla config set default-vin <VIN>",
        "error.token_expired": "Token scaduto. Eseguire: tesla config auth order",
        "error.vehicle_not_found": "Veicolo {vin} non trovato su questo account",
        "error.api": "Errore API {code}: {message}",
        # Configurazione iniziale
        "setup.welcome": "Benvenuto in tesla-cli! Configuriamo il tuo account.",
        "setup.step": "Passo {n} / {total} — {label}",
        "setup.done": "Configurazione completata! Eseguire tesla --help per i comandi disponibili.",
        "setup.skip": "(saltato)",
        "setup.found_order": "Ordine trovato: {model} — {status}",
        "setup.vin_not_assigned": "VIN non ancora assegnato — solo il numero di prenotazione salvato.",
        "setup.multiple_orders": "Più ordini trovati — selezionarne uno:",
    },
}
