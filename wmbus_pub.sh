#!/bin/bash
export LC_ALL=C
# Erweiterter MQTT-Publisher für wmbusmeters - ALLE DATEN
JSON="$1"; NAME="$2"; ID="$3"

MOSQ=$(command -v mosquitto_pub)
JQ=$(command -v jq)
BROKER="-h 192.168.68.99 -u mqttuser -P 310192 -q 1"
DISC_PREFIX="homeassistant"
DEV_ID="wmbus_${ID}"
DEV_NAME="${NAME} (${ID})"

HEARTBEAT=60
MIN_ACTIVE_INTERVAL=5
THRESHOLD_TEMP_C=0.05
THRESHOLD_TOTAL_M3=0.001

STATE_DIR="/var/tmp"
STATE_FILE="${STATE_DIR}/wmbus_${ID}.last"
DISC_STATE="${STATE_DIR}/wmbus_${ID}.disc"
mkdir -p "$STATE_DIR"

log(){ logger -t wmbus2mqtt "$*"; }

publish_state() {
  echo "$JSON" | $MOSQ $BROKER -r -t "wmbus/${NAME}/state" -l
}

publish_discovery_for_key() {
  KEY="$1"; SID="$2"; PNAME="$3"; UNIT="$4"; DEVCLA="$5"; STATECLASS="$6"; ICON="$7"
  VALTPL="{{ value_json.${KEY} }}"
  PAYLOAD="{\"name\":\"${PNAME}\",\"uniq_id\":\"wmbus_${NAME}_${SID}\",\"stat_t\":\"wmbus/${NAME}/state\",\"val_tpl\":\"${VALTPL}\""
  [ -n "$UNIT" ] && PAYLOAD="${PAYLOAD},\"unit_of_meas\":\"${UNIT}\""
  [ -n "$DEVCLA" ] && PAYLOAD="${PAYLOAD},\"dev_cla\":\"${DEVCLA}\""
  [ -n "$STATECLASS" ] && PAYLOAD="${PAYLOAD},\"state_class\":\"${STATECLASS}\""
  [ -n "$ICON" ] && PAYLOAD="${PAYLOAD},\"icon\":\"${ICON}\""
  PAYLOAD="${PAYLOAD},\"dev\":{\"ids\":[\"${DEV_ID}\"],\"name\":\"${DEV_NAME}\",\"mf\":\"Diehl\",\"mdl\":\"Hydrus\",\"sw\":\"wmbusmeters\"}}"
  $MOSQ $BROKER -r -t "${DISC_PREFIX}/sensor/${NAME}_${SID}/config" -m "$PAYLOAD"
}

# Alle Daten aus Log extrahieren - direkt ohne BLOCK variable
extract_additional_data() {
  LOG_FILE="/var/log/wmbusmeters/wmbusmeters.log"
  [ ! -f "$LOG_FILE" ] && return

  # Storage 8 Volume (049 C?) - direkt aus Log
  LINE_VOL=$(tail -200 "$LOG_FILE" | grep "(hydrus) 049 C" | tail -1)
  if [ -n "$LINE_VOL" ]; then
    RAW=$(echo "$LINE_VOL" | cut -d' ' -f4)
    if [ -n "$RAW" ] && [ ${#RAW} -eq 8 ]; then
      B1=${RAW:0:2}; B2=${RAW:2:2}; B3=${RAW:4:2}; B4=${RAW:6:2}
      REVERSED="${B4}${B3}${B2}${B1}"
      REVERSED=${REVERSED#"${REVERSED%%[!0]*}"}
      [ -z "$REVERSED" ] && REVERSED=0
      HIST_VOL=$(awk "BEGIN{printf \"%.2f\", $REVERSED/100}")
      echo "HIST_VOL=$HIST_VOL"
    fi
  fi

  # Storage 8 DateTime (042 C?) - direkt aus Log
  LINE_DT=$(tail -200 "$LOG_FILE" | grep "(hydrus) 042 C" | tail -1)
  if [ -n "$LINE_DT" ]; then
    RAW=$(echo "$LINE_DT" | cut -d' ' -f4)
    if [ -n "$RAW" ] && [ ${#RAW} -eq 8 ]; then
      # CP32 datetime decode
      B0=$((16#${RAW:0:2}))
      B1=$((16#${RAW:2:2}))
      B2=$((16#${RAW:4:2}))
      B3=$((16#${RAW:6:2}))

      MINUTE=$B0
      HOUR=$((B1 & 31))
      DAY=$((B2 & 31))
      YEAR_LO=$(((B2 >> 5) & 7))
      MONTH=$((B3 & 15))
      YEAR_HI=$(((B3 >> 4) & 15))
      YEAR=$((2000 + (YEAR_HI << 3) + YEAR_LO))

      BILLING_DATE=$(printf "%04d-%02d-%02d %02d:%02d" $YEAR $MONTH $DAY $HOUR $MINUTE)
      echo "BILLING_DATE='$BILLING_DATE'"
    fi
  fi

  # Error flags (035 C?) - direkt aus Log
  LINE_ERR=$(tail -200 "$LOG_FILE" | grep "(hydrus) 035 C" | tail -1)
  if [ -n "$LINE_ERR" ]; then
    ERR_RAW=$(echo "$LINE_ERR" | cut -d' ' -f4)
    if [ "$ERR_RAW" = "00000000" ]; then
      echo "ERROR_STATUS='OK'"
    else
      echo "ERROR_STATUS='ERROR:$ERR_RAW'"
    fi
  fi
}


log "RUN shell for meter name=${NAME} id=${ID}"

# Basis-Werte aus JSON
if [ -n "$JQ" ]; then
  TEMP=$(echo "$JSON" | $JQ -r ".flow_temperature_c // empty")
  TOTAL_M3=$(echo "$JSON" | $JQ -r ".total_m3 // empty")
  RSSI=$(echo "$JSON" | $JQ -r ".rssi_dbm // empty")
  BATTERY=$(echo "$JSON" | $JQ -r ".remaining_battery_life_y // empty")
  STATUS=$(echo "$JSON" | $JQ -r ".status // empty")
else
  TEMP=""; TOTAL_M3=""; RSSI=""; BATTERY=""; STATUS=""
fi

# Zusätzliche Daten aus Log extrahieren
HIST_VOL=""; BILLING_DATE=""; ERROR_STATUS=""
eval $(extract_additional_data)
HIST_M3="${HIST_VOL:-}"


# Verbrauch seit Abrechnung
CONSUMPTION_M3=""
if [ -n "$TOTAL_M3" ] && [ -n "$HIST_M3" ]; then
  CONSUMPTION_M3=$(awk "BEGIN{printf \"%.2f\", $TOTAL_M3 - $HIST_M3}")
fi

# Vorzustand laden
LAST_TEMP=""; LAST_TOTAL_M3=""; LAST_TS=0
[ -f "$STATE_FILE" ] && . "$STATE_FILE"
NOW=$(date +%s)
AGE=$((NOW - LAST_TS))

# Änderungsdetektion
need_publish=0
if [ -n "$TEMP" ] && [ -n "$LAST_TEMP" ]; then
  DT=$(awk "BEGIN{t=$TEMP-$LAST_TEMP; if(t<0)t=-t; print t}")
  [ "$(awk "BEGIN{print ($DT >= $THRESHOLD_TEMP_C)}")" = "1" ] && need_publish=1
fi
if [ -n "$TOTAL_M3" ] && [ -n "$LAST_TOTAL_M3" ]; then
  DV=$(awk "BEGIN{v=$TOTAL_M3-$LAST_TOTAL_M3; if(v<0)v=-v; print v}")
  [ "$(awk "BEGIN{print ($DV >= $THRESHOLD_TOTAL_M3)}")" = "1" ] && need_publish=1
fi
[ "$AGE" -ge "$HEARTBEAT" ] && need_publish=1
[ "$need_publish" -eq 1 ] && [ "$AGE" -lt "$MIN_ACTIVE_INTERVAL" ] && need_publish=0

# Discovery check
publish_discovery=0
if [ ! -f "$DISC_STATE" ]; then
  publish_discovery=1
else
  DISC_AGE=$((NOW - $(cat "$DISC_STATE" 2>/dev/null || echo 0)))
  [ "$DISC_AGE" -ge 3600 ] && publish_discovery=1
fi

if [ "$need_publish" -eq 1 ]; then
  # JSON erweitern mit ALLEN Daten
  if [ -n "$JQ" ]; then
    TOTAL_L=$(awk "BEGIN{printf \"%.0f\", ${TOTAL_M3:-0} * 1000}")
    JSON=$(echo "$JSON" | $JQ -c \
      --arg hist "${HIST_M3:-}" \
      --arg cons "${CONSUMPTION_M3:-}" \
      --arg total_l "$TOTAL_L" \
      --arg billing_date "${BILLING_DATE:-}" \
      --arg error_status "${ERROR_STATUS:-OK}" \
      '. + {
        total_liters: ($total_l | tonumber),
        historical_m3: (if $hist != "" then ($hist | tonumber) else null end),
        consumption_since_billing_m3: (if $cons != "" then ($cons | tonumber) else null end),
        billing_date: (if $billing_date != "" then $billing_date else null end),
        meter_error_status: $error_status
      }')
  fi

  # Publish state
  publish_state || { log "ERROR publish state"; exit 1; }

  # Discovery für ALLE Sensoren
  if [ "$publish_discovery" -eq 1 ]; then
    publish_discovery_for_key "total_m3" "total_m3" "Total" "m³" "water" "total_increasing" "mdi:water"
    publish_discovery_for_key "total_liters" "total_liters" "Total Liters" "L" "water" "total_increasing" "mdi:water"
    publish_discovery_for_key "flow_temperature_c" "flow_temp" "Water Temperature" "°C" "temperature" "measurement" ""
    publish_discovery_for_key "remaining_battery_life_y" "battery_years" "Battery Life" "y" "" "measurement" "mdi:battery"
    publish_discovery_for_key "rssi_dbm" "rssi" "Signal Strength" "dBm" "signal_strength" "measurement" ""
    publish_discovery_for_key "historical_m3" "historical" "Last Billing Reading" "m³" "water" "total" "mdi:history"
    publish_discovery_for_key "consumption_since_billing_m3" "consumption" "Consumption Since Billing" "m³" "water" "total_increasing" "mdi:chart-line"
    publish_discovery_for_key "billing_date" "billing_date" "Billing Date" "" "" "" "mdi:calendar"
    publish_discovery_for_key "meter_error_status" "error_status" "Meter Status" "" "" "" "mdi:alert-circle"
    publish_discovery_for_key "status" "comm_status" "Communication Status" "" "" "" "mdi:lan-connect"
    publish_discovery_for_key "timestamp" "last_sync" "Last Sync" "" "timestamp" "" "mdi:clock-outline"
    echo "$NOW" > "$DISC_STATE"
  fi

  # State speichern
  printf "LAST_TS=%s\n" "$NOW" > "$STATE_FILE"
  [ -n "$TEMP" ] && printf "LAST_TEMP=%s\n" "$TEMP" >> "$STATE_FILE"
  [ -n "$TOTAL_M3" ] && printf "LAST_TOTAL_M3=%s\n" "$TOTAL_M3" >> "$STATE_FILE"

  log "OK published total=${TOTAL_M3}m3 temp=${TEMP}C hist=${HIST_M3}m3 billing=${BILLING_DATE} errors=${ERROR_STATUS}"
else
  log "SKIP (age=${AGE}s)"
fi
