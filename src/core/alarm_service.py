"""
Alarm service and notification management for Croquis application
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

from core.key_manager import decrypt_data
from utils.log_manager import LOG_MESSAGES


logger = logging.getLogger('Croquis')


def get_data_path():
    """Get base path for data files"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent


def get_icon_path():
    """Get the icon file path for toast notifications.
    For compiled executables, icon.ico is bundled into _MEIPASS."""
    if getattr(sys, 'frozen', False):
        # Compiled executable: icon is in _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        else:
            icon_path = Path(sys.executable).parent / "icon.ico"
    else:
        # Script mode: icon is in src/assets directory
        icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    
    return str(icon_path) if icon_path.exists() else None


def show_toast_notification(title: str, message: str, icon_path: str = None):
    """Display Windows toast notification"""
    # Set icon path
    if icon_path is None:
        icon_path = get_icon_path()
    
    icon_exists = icon_path and os.path.exists(icon_path)
    logger.info(LOG_MESSAGES["toast_notification_requested"].format(title, message, icon_path))
    logger.info(f"Icon exists: {icon_exists}")
    
    # Priority 1: win11toast (Windows 10/11 native notifications)
    try:
        from win11toast import toast_async
        import asyncio
        
        async def show_toast():
            # 5 second timeout
            try:
                await asyncio.wait_for(
                    toast_async(
                        title,
                        message,
                        icon=icon_path if icon_exists else None,
                        app_id="Croquis"
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(LOG_MESSAGES["toast_notification_timeout"])
        
        asyncio.run(show_toast())
        logger.info(LOG_MESSAGES["toast_notification_success"].format("win11toast"))
        return
    except Exception as e:
        logger.error(LOG_MESSAGES["toast_notification_failed"].format("win11toast", e))
    
    # Priority 2: plyer (cross-platform)
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Croquis",
            app_icon=icon_path if icon_exists else None,
            timeout=10
        )
        logger.info(LOG_MESSAGES["toast_notification_success"].format("plyer"))
        return
    except Exception as e:
        logger.error(LOG_MESSAGES["toast_notification_failed"].format("plyer", e))
    
    # Last resort: console output
    fallback_msg = f"[ALARM] {title}: {message}"
    print(fallback_msg)
    logger.info(LOG_MESSAGES["toast_notification_fallback"].format(fallback_msg))


def check_and_trigger_alarms():
    """Check and trigger alarms (prevent duplicates)"""
    dat_dir = get_data_path() / "dat"
    alarms_file = dat_dir / "alarms.dat"
    
    if not alarms_file.exists():
        return
    
    try:
        with open(alarms_file, "rb") as f:
            encrypted = f.read()
        data = decrypt_data(encrypted)
        alarms = data.get("alarms", [])
        
        if not alarms:
            return
        
        logger.info(LOG_MESSAGES["alarm_checking"].format(len(alarms)))
        
        # Current time
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        current_weekday = now.weekday()
        icon_path = get_icon_path()
        
        # Check alarms
        for i, alarm in enumerate(alarms):
            if not alarm.get("enabled", False):
                continue
            
            alarm_time = alarm.get("time", "")
            alarm_type = alarm.get("type", "")
            
            # Check time match
            if alarm_time != current_time:
                continue
            
            # Check by type
            should_trigger = False
            
            if alarm_type == "weekday":
                weekdays = alarm.get("weekdays", [])
                if current_weekday in weekdays:
                    should_trigger = True
            elif alarm_type == "date":
                alarm_date = alarm.get("date", "")
                if alarm_date == current_date:
                    should_trigger = True
            
            if should_trigger:
                title = alarm.get("title", "Croquis Alarm")
                message = alarm.get("message", "Time to practice croquis!")
                logger.info(LOG_MESSAGES["alarm_triggered"].format(title, current_time))
                show_toast_notification(title, message, icon_path)
                
    except Exception as e:
        logger.error(LOG_MESSAGES["alarm_check_failed"].format(e))


def setup_alarm_background_service():
    """BAT 파일을 ANSI 인코딩으로 생성하고 Windows 시작프로그램에 등록"""
    try:
        # 컴파일된 실행 파일만 등록
        if not getattr(sys, 'frozen', False):
            logger.info("Development mode - skipping background service setup")
            return True
        
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
        
        # BAT 파일 생성 (1분마다 알람 체크) - ANSI(CP949) 인코딩
        bat_content = f"""@echo off
title Croquis Alarm Service
cd /d "{exe_dir}"
:loop
start /b /wait "" "{exe_path}" --check-alarm
timeout /t 60 /nobreak >nul
goto loop
"""
        
        bat_path = exe_dir / "croquis_alarm_service.bat"
        with open(bat_path, "w", encoding="cp949") as f:
            f.write(bat_content)
        
        # VBS 파일 생성 (BAT를 보이지 않게 실행) - 절대 경로 사용
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{bat_path}""", 0, False
Set WshShell = Nothing
'''
        
        vbs_path = exe_dir / "croquis_alarm_service.vbs"
        with open(vbs_path, "w", encoding="cp949") as f:
            f.write(vbs_content)
        
        # Windows 시작프로그램 폴더 경로
        startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_link = startup_folder / "Croquis_Alarm.vbs"
        
        # 기존 링크 삭제
        if startup_link.exists():
            startup_link.unlink()
        
        # Copy VBS file to startup folder
        import shutil
        shutil.copy2(vbs_path, startup_link)
        
        logger.info(LOG_MESSAGES["alarm_service_installed"])
        return True
        
    except Exception as e:
        logger.warning(f"Failed to setup alarm background service: {e}")
        return False


def remove_alarm_background_service():
    """Remove BAT file and startup registration"""
    try:
        exe_dir = get_data_path()
        
        # Delete BAT, VBS, Python files
        bat_path = exe_dir / "croquis_alarm_service.bat"
        vbs_path = exe_dir / "croquis_alarm_service.vbs"
        py_path = exe_dir / "croquis_alarm_background.py"
        
        if bat_path.exists():
            bat_path.unlink()
        if vbs_path.exists():
            vbs_path.unlink()
        if py_path.exists():
            py_path.unlink()
        
        # Remove from startup folder
        startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_link = startup_folder / "Croquis_Alarm.vbs"
        
        if startup_link.exists():
            startup_link.unlink()
        
        logger.info(LOG_MESSAGES["alarm_service_removed"])
        return True
        
    except Exception as e:
        logger.warning(f"Failed to remove alarm background service: {e}")
        return False
