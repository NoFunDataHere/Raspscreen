#!/usr/bin/env bash
# ==========================================================
# RaspEcran - Contrôle de mise en veille de l'écran DSI 7"
# ==========================================================

ACTION="$1"

# Chemins possibles du rétroéclairage
BL_PATHS=(
    "/sys/class/backlight/rpi_backlight/bl_power"
    "/sys/class/backlight/10-0045/bl_power"
    "/sys/class/backlight/soc:backlight/bl_power"
)

turn_off() {
    echo "[Screen] Extinction de l'écran (mise en veille)..."
    for p in "${BL_PATHS[@]}"; do
        if [ -w "$p" ]; then
            echo 1 > "$p"
            return 0
        elif [ -f "$p" ]; then
            sudo sh -c "echo 1 > $p"
            return 0
        fi
    done
    
    # Wayland fallback
    if command -v wlr-randr > /dev/null 2>&1; then
        wlr-randr --output DSI-1 --off 2>/dev/null && return 0
    fi
    
    # X11 fallback
    if command -v xset > /dev/null 2>&1; then
        xset dpms force off 2>/dev/null && return 0
    fi
}

BRIGHTNESS_PATHS=(
    "/sys/class/backlight/rpi_backlight/brightness"
    "/sys/class/backlight/10-0045/brightness"
    "/sys/class/backlight/soc:backlight/brightness"
)

dim() {
    echo "[Screen] Atténuation du rétroéclairage (15/255)..."
    for p in "${BRIGHTNESS_PATHS[@]}"; do
        if [ -w "$p" ]; then
            echo 15 > "$p"
            return 0
        elif [ -f "$p" ]; then
            sudo sh -c "echo 15 > $p"
            return 0
        fi
    done
}

turn_on() {
    echo "[Screen] Rallumage de l'écran et pleine luminosité..."
    for p in "${BL_PATHS[@]}"; do
        if [ -w "$p" ]; then
            echo 0 > "$p"
        elif [ -f "$p" ]; then
            sudo sh -c "echo 0 > $p"
        fi
    done
    for p in "${BRIGHTNESS_PATHS[@]}"; do
        if [ -w "$p" ]; then
            echo 255 > "$p"
        elif [ -f "$p" ]; then
            sudo sh -c "echo 255 > $p"
        fi
    done
    
    # Wayland fallback
    if command -v wlr-randr > /dev/null 2>&1; then
        wlr-randr --output DSI-1 --on 2>/dev/null && return 0
    fi
    
    # X11 fallback
    if command -v xset > /dev/null 2>&1; then
        xset dpms force on 2>/dev/null && return 0
    fi
}

case "$ACTION" in
    dim)
        dim
        ;;
    off|sleep)
        turn_off
        ;;
    on|wake)
        turn_on
        ;;
    *)
        echo "Usage: $0 {dim|off|sleep|on|wake}"
        exit 1
        ;;
esac
