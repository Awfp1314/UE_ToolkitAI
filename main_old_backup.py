# -*- coding: utf-8 -*-

"""
铏氬够寮曟搸宸ュ叿绠变富鍏ュ彛
"""

import sys
import os
import time
from pathlib import Path

# 娣诲姞椤圭洰鏍圭洰褰曞埌Python璺緞
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QStandardPaths, QTimer
from PyQt6.QtGui import QIcon
from ui.ue_main_window import UEMainWindow
from core.app_manager import AppManager
from core.logger import init_logging_system, get_logger, setup_console_encoding
from core.single_instance import SingleInstanceManager
from core.utils.style_system import style_system  # 猸?瀵煎叆鏍峰紡绯荤粺
import json

# 鈿?璁剧疆鎺у埗鍙扮紪鐮佷负 UTF-8锛圵indows 骞冲彴锛?
setup_console_encoding()

init_logging_system()
logger = get_logger(__name__)


def set_windows_app_user_model_id():
    """璁剧疆 Windows AppUserModelID锛岀‘淇濅换鍔℃爮鍥炬爣姝ｇ‘鏄剧ず"""
    try:
        import ctypes
        app_id = 'HUTAO.UEToolkit.1.0'  # 搴旂敤绋嬪簭鍞竴鏍囪瘑绗?
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.info(f"宸茶缃?Windows AppUserModelID: {app_id}")
    except Exception as e:
        logger.warning(f"璁剧疆 Windows AppUserModelID 澶辫触: {e}")


def main():
    """涓诲嚱鏁?""
    # 鈿?鎬ц兘浼樺寲锛氳褰曞惎鍔ㄦ椂闂达紙Requirement 16.5锛?
    startup_start_time = time.time()

    # 鍒涘缓搴旂敤瀹炰緥
    app = QApplication(sys.argv)
    app.setApplicationName("ue_toolkit")  # 缁熶竴浣跨敤鏃犵┖鏍肩殑鍚嶇О
    app.setApplicationVersion("1.0.1")

    # 鈿?浼樺寲锛氱珛鍗冲垱寤哄苟鏄剧ず鍚姩鍔犺浇鐣岄潰锛堝湪杈撳嚭浠讳綍鏃ュ織涔嬪墠锛?
    from ui.splash_screen import SplashScreen
    # 鏍规嵁QSS涓婚閫夋嫨鍚姩鐣岄潰涓婚
    current_theme = "modern_dark"  # 榛樿涓婚
    splash_theme = "dark" if "dark" in current_theme.lower() else "light"
    splash = SplashScreen(theme=splash_theme)

    # 鈿?鍏抽敭锛氬湪鏄剧ず鍚姩鐣岄潰涔嬪墠灏辨敞鍐屾棩蹇楀鐞嗗櫒锛岀‘淇濇崟鑾锋墍鏈夋棩蹇?
    splash.register_log_handler()

    splash.show()
    app.processEvents()  # 寮哄埗鍒锋柊UI锛岀‘淇濆惎鍔ㄧ晫闈㈢珛鍗虫樉绀?

    # 鐜板湪寮€濮嬭緭鍑烘棩蹇楋紝杩欎簺鏃ュ織浼氳鎹曡幏骞舵洿鏂拌繘搴︽潯
    logger.info("鍚姩铏氬够寮曟搸宸ュ叿绠?)
    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

    # 璁剧疆 Windows 浠诲姟鏍忓浘鏍?
    if sys.platform == 'win32':
        set_windows_app_user_model_id()
    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

    # 璁剧疆搴旂敤绋嬪簭鍥炬爣
    icon_path = project_root / "resources" / "tubiao.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.info(f"宸茶缃簲鐢ㄥ浘鏍? {icon_path}")
    else:
        logger.warning(f"鍥炬爣鏂囦欢涓嶅瓨鍦? {icon_path}")
    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

    # 猸?鍔犺浇淇濆瓨鐨勪富棰樿缃?
    try:
        app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        config_path = Path(app_data) / "ue_toolkit" / "ui_settings.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            saved_theme = config.get('theme', 'modern_dark')

            # 鍏煎鏃х増鏈厤缃細濡傛灉淇濆瓨鐨勬槸 'dark' 鎴?'light'锛屾槧灏勫埌鏂扮殑涓婚鍚嶇О
            theme_mapping = {
                'dark': 'modern_dark',
                'light': 'modern_light'
            }
            current_theme = theme_mapping.get(saved_theme, saved_theme)

            logger.info(f"宸插姞杞戒繚瀛樼殑涓婚: {saved_theme} -> {current_theme}")
        else:
            logger.info("鏈壘鍒颁富棰橀厤缃紝浣跨敤榛樿涓婚: modern_dark")
    except Exception as e:
        logger.warning(f"鍔犺浇涓婚璁剧疆澶辫触锛屼娇鐢ㄩ粯璁や富棰? {e}")

    # 猸?搴旂敤QSS涓婚锛堝湪鍒涘缓浠讳綍绐楀彛涔嬪墠锛?
    logger.info(f"姝ｅ湪搴旂敤QSS涓婚: {current_theme}...")
    style_system.apply_theme(app, current_theme)
    logger.info("鉁?QSS涓婚搴旂敤鎴愬姛")
    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

    logger.info("鍚姩鍔犺浇鐣岄潰宸叉樉绀?)
    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

    # 妫€鏌ュ崟瀹炰緥锛堟棩蹇椾細鑷姩鏇存柊杩涘害鏉★級
    single_instance = SingleInstanceManager("UEToolkit")
    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

    if single_instance.is_running():
        logger.info("绋嬪簭宸茬粡鍦ㄨ繍琛岋紝婵€娲荤幇鏈夊疄渚?)
        splash.close()
        return 0

    try:
        # 鍒涘缓搴旂敤绠＄悊鍣紙鏃ュ織浼氳嚜鍔ㄦ洿鏂拌繘搴︽潯锛?
        app_manager = AppManager()
        app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

        # 璁剧疆搴旂敤绋嬪簭锛堟棩蹇椾細鑷姩鏇存柊杩涘害鏉★級
        logger.info("寮€濮嬭缃簲鐢ㄧ▼搴?)
        app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

        if not app_manager.setup():
            logger.error("搴旂敤绋嬪簭璁剧疆澶辫触")
            splash.close()
            QMessageBox.critical(None, "鍚姩澶辫触", "搴旂敤绋嬪簭璁剧疆澶辫触锛岃鏌ョ湅鏃ュ織鏂囦欢鑾峰彇璇︾粏淇℃伅銆?)
            return 1

        logger.info("搴旂敤绋嬪簭璁剧疆鎴愬姛")
        app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

        # 瀛樺偍涓荤獥鍙ｅ紩鐢紙鍦ㄥ洖璋冧腑浣跨敤锛?
        main_window = None
        module_provider = None

        def on_startup_complete(success: bool):
            """寮傛鍚姩瀹屾垚鍥炶皟"""
            nonlocal main_window, module_provider, splash
            
            if not success:
                logger.error("搴旂敤绋嬪簭鍚姩澶辫触")
                QMessageBox.critical(
                    None, 
                    "鍚姩澶辫触", 
                    "搴旂敤绋嬪簭鍚姩澶辫触锛岃鏌ョ湅鏃ュ織鏂囦欢鑾峰彇璇︾粏淇℃伅銆?
                )
                app.quit()
                return
            
            try:
                logger.info("搴旂敤绋嬪簭鍚姩鎴愬姛")
                app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

                # 鍒涘缓妯″潡鎻愪緵鑰咃紙鏃ュ織浼氳嚜鍔ㄦ洿鏂拌繘搴︽潯锛?
                from core.module_interface import ModuleProviderAdapter
                module_provider = ModuleProviderAdapter(app_manager.module_manager)
                app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

                # 寤虹珛妯″潡闂寸殑杩炴帴锛圓I鍔╂墜銆佽祫浜х鐞嗗櫒銆侀厤缃伐鍏凤級
                try:
                    logger.info("========== 寮€濮嬪缓绔嬫ā鍧楅棿杩炴帴 ==========")
                    print("[DEBUG] ========== 寮€濮嬪缓绔嬫ā鍧楅棿杩炴帴 ==========")
                    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

                    if not app_manager.module_manager:
                        print("[DEBUG] [ERROR] module_manager 鏈垵濮嬪寲")
                        raise RuntimeError("module_manager 鏈垵濮嬪寲")

                    asset_manager_module = app_manager.module_manager.get_module("asset_manager")
                    config_tool_module = app_manager.module_manager.get_module("config_tool")
                    ai_assistant_module = app_manager.module_manager.get_module("ai_assistant")
                    app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊
                    
                    print(f"[DEBUG] asset_manager 妯″潡: {asset_manager_module}")
                    print(f"[DEBUG] config_tool 妯″潡: {config_tool_module}")
                    print(f"[DEBUG] ai_assistant 妯″潡: {ai_assistant_module}")
                    
                    if ai_assistant_module:
                        print(f"[DEBUG] ai_assistant 瀹炰緥: {ai_assistant_module.instance}")

                        # 杩炴帴 asset_manager
                        if asset_manager_module and asset_manager_module.instance:
                            print(f"[DEBUG] asset_manager 瀹炰緥: {asset_manager_module.instance}")
                            
                            # 鑾峰彇 asset_manager 鐨勯€昏緫灞傚疄渚?
                            if hasattr(asset_manager_module.instance, 'logic'):
                                asset_logic = asset_manager_module.instance.logic  # type: ignore
                                print(f"[DEBUG] [OK] 閫氳繃 .logic 灞炴€ц幏鍙栧埌 asset_manager 閫昏緫灞? {asset_logic}")
                                logger.info("鑾峰彇鍒?asset_manager 閫昏緫灞?)
                            elif asset_manager_module.instance and hasattr(asset_manager_module.instance, 'get_logic'):
                                asset_logic = asset_manager_module.instance.get_logic()  # type: ignore
                                print(f"[DEBUG] [OK] 閫氳繃 get_logic() 鑾峰彇鍒?asset_manager 閫昏緫灞? {asset_logic}")
                                logger.info("閫氳繃 get_logic 鑾峰彇鍒?asset_manager 閫昏緫灞?)
                            else:
                                asset_logic = None
                                print("[DEBUG] [ERROR] 鏃犳硶鑾峰彇 asset_manager 閫昏緫灞?)
                                logger.warning("鏃犳硶鑾峰彇 asset_manager 閫昏緫灞?)
                            
                            # 灏?asset_manager 閫昏緫灞備紶閫掔粰 AI鍔╂墜
                            if asset_logic and ai_assistant_module.instance and hasattr(ai_assistant_module.instance, 'set_asset_manager_logic'):
                                print(f"[DEBUG] 姝ｅ湪璋冪敤 ai_assistant.set_asset_manager_logic({asset_logic})...")
                                ai_assistant_module.instance.set_asset_manager_logic(asset_logic)  # type: ignore
                                print("[DEBUG] [OK] 宸插皢 asset_manager 閫昏緫灞傝繛鎺ュ埌 AI鍔╂墜")
                                logger.info("宸插皢 asset_manager 閫昏緫灞傝繛鎺ュ埌 AI鍔╂墜")
                            else:
                                if not asset_logic:
                                    print("[DEBUG] [ERROR] asset_logic 涓?None锛屾棤娉曡繛鎺?)
                                if ai_assistant_module.instance and not hasattr(ai_assistant_module.instance, 'set_asset_manager_logic'):
                                    print("[DEBUG] [ERROR] AI鍔╂墜妯″潡缂哄皯 set_asset_manager_logic 鏂规硶")
                                    logger.warning("AI鍔╂墜妯″潡缂哄皯 set_asset_manager_logic 鏂规硶")
                        else:
                            print("[DEBUG] [WARN] asset_manager 妯″潡鏈姞杞?)
                            logger.info("asset_manager 妯″潡鏈姞杞斤紝璺宠繃杩炴帴")
                        
                        # 杩炴帴 config_tool
                        if config_tool_module and config_tool_module.instance:
                            print(f"[DEBUG] config_tool 瀹炰緥: {config_tool_module.instance}")
                            
                            # 鑾峰彇 config_tool 鐨勯€昏緫灞傚疄渚?
                            if hasattr(config_tool_module.instance, 'logic'):
                                config_logic = config_tool_module.instance.logic  # type: ignore
                                print(f"[DEBUG] [OK] 閫氳繃 .logic 灞炴€ц幏鍙栧埌 config_tool 閫昏緫灞? {config_logic}")
                                logger.info("鑾峰彇鍒?config_tool 閫昏緫灞?)
                            elif config_tool_module.instance and hasattr(config_tool_module.instance, 'get_logic'):
                                config_logic = config_tool_module.instance.get_logic()  # type: ignore
                                print(f"[DEBUG] [OK] 閫氳繃 get_logic() 鑾峰彇鍒?config_tool 閫昏緫灞? {config_logic}")
                                logger.info("閫氳繃 get_logic 鑾峰彇鍒?config_tool 閫昏緫灞?)
                            else:
                                config_logic = None
                                print("[DEBUG] [ERROR] 鏃犳硶鑾峰彇 config_tool 閫昏緫灞?)
                                logger.warning("鏃犳硶鑾峰彇 config_tool 閫昏緫灞?)
                            
                            # 灏?config_tool 閫昏緫灞備紶閫掔粰 AI鍔╂墜
                            if config_logic and ai_assistant_module.instance and hasattr(ai_assistant_module.instance, 'set_config_tool_logic'):
                                print(f"[DEBUG] 姝ｅ湪璋冪敤 ai_assistant.set_config_tool_logic({config_logic})...")
                                ai_assistant_module.instance.set_config_tool_logic(config_logic)  # type: ignore
                                print("[DEBUG] [OK] 宸插皢 config_tool 閫昏緫灞傝繛鎺ュ埌 AI鍔╂墜")
                                logger.info("宸插皢 config_tool 閫昏緫灞傝繛鎺ュ埌 AI鍔╂墜")
                            else:
                                if not config_logic:
                                    print("[DEBUG] [ERROR] config_logic 涓?None锛屾棤娉曡繛鎺?)
                                if ai_assistant_module.instance and not hasattr(ai_assistant_module.instance, 'set_config_tool_logic'):
                                    print("[DEBUG] [ERROR] AI鍔╂墜妯″潡缂哄皯 set_config_tool_logic 鏂规硶")
                                    logger.warning("AI鍔╂墜妯″潡缂哄皯 set_config_tool_logic 鏂规硶")
                        else:
                            print("[DEBUG] [WARN] config_tool 妯″潡鏈姞杞?)
                            logger.info("config_tool 妯″潡鏈姞杞斤紝璺宠繃杩炴帴")
                        
                        # 杩炴帴 site_recommendations
                        site_recommendations_module = module_provider.get_module("site_recommendations")
                        if site_recommendations_module and site_recommendations_module.instance:  # type: ignore
                            print(f"[DEBUG] site_recommendations 瀹炰緥: {site_recommendations_module.instance}")  # type: ignore
                            
                            # 鑾峰彇 site_recommendations 鐨勯€昏緫灞傚疄渚?
                            if hasattr(site_recommendations_module.instance, 'logic'):  # type: ignore
                                site_logic = site_recommendations_module.instance.logic  # type: ignore
                                print(f"[DEBUG] [OK] 閫氳繃 .logic 灞炴€ц幏鍙栧埌 site_recommendations 閫昏緫灞? {site_logic}")
                                logger.info("鑾峰彇鍒?site_recommendations 閫昏緫灞?)
                            elif site_recommendations_module.instance and hasattr(site_recommendations_module.instance, 'get_logic'):  # type: ignore
                                site_logic = site_recommendations_module.instance.get_logic()  # type: ignore
                                print(f"[DEBUG] [OK] 閫氳繃 get_logic() 鑾峰彇鍒?site_recommendations 閫昏緫灞? {site_logic}")
                                logger.info("閫氳繃 get_logic 鑾峰彇鍒?site_recommendations 閫昏緫灞?)
                            else:
                                site_logic = None
                                print("[DEBUG] [ERROR] 鏃犳硶鑾峰彇 site_recommendations 閫昏緫灞?)
                                logger.warning("鏃犳硶鑾峰彇 site_recommendations 閫昏緫灞?)
                            
                            # 灏?site_recommendations 閫昏緫灞備紶閫掔粰 AI鍔╂墜
                            if site_logic and ai_assistant_module.instance and hasattr(ai_assistant_module.instance, 'site_recommendations_logic'):  # type: ignore
                                print(f"[DEBUG] 姝ｅ湪璁剧疆 ai_assistant.site_recommendations_logic = {site_logic}")
                                ai_assistant_module.instance.site_recommendations_logic = site_logic  # type: ignore
                                print("[DEBUG] [OK] 宸插皢 site_recommendations 閫昏緫灞傝繛鎺ュ埌 AI鍔╂墜")
                                logger.info("宸插皢 site_recommendations 閫昏緫灞傝繛鎺ュ埌 AI鍔╂墜")
                            else:
                                if not site_logic:
                                    print("[DEBUG] [ERROR] site_logic 涓?None锛屾棤娉曡繛鎺?)
                                if ai_assistant_module.instance and not hasattr(ai_assistant_module.instance, 'site_recommendations_logic'):
                                    print("[DEBUG] [ERROR] AI鍔╂墜妯″潡缂哄皯 site_recommendations_logic 灞炴€?)
                                    logger.warning("AI鍔╂墜妯″潡缂哄皯 site_recommendations_logic 灞炴€?)
                        else:
                            print("[DEBUG] [WARN] site_recommendations 妯″潡鏈姞杞?)
                            logger.info("site_recommendations 妯″潡鏈姞杞斤紝璺宠繃杩炴帴")
                    else:
                        print("[DEBUG] [WARN] ai_assistant 妯″潡鏈姞杞?)
                        logger.info("ai_assistant 妯″潡鏈姞杞斤紝璺宠繃杩炴帴")
                    
                    print("[DEBUG] ========== 妯″潡杩炴帴娴佺▼缁撴潫 ==========")
                except Exception as e:
                    print(f"[DEBUG] [ERROR] 寤虹珛妯″潡闂磋繛鎺ユ椂鍙戠敓寮傚父: {e}")
                    logger.error(f"寤虹珛妯″潡闂磋繛鎺ュけ璐? {e}", exc_info=True)
                    import traceback
                    traceback.print_exc()
                
                # 鍒涘缓涓荤獥鍙ｏ紙浣嗕笉鏄剧ず锛夛紙鏃ュ織浼氳嚜鍔ㄦ洿鏂拌繘搴︽潯锛?
                logger.info("鍒涘缓涓荤獥鍙?)
                app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊
                main_window = UEMainWindow(module_provider)
                app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

                # 鈿?浼樺寲锛氫笉鍦ㄥ惎鍔ㄦ椂棰勫姞杞借祫浜э紝璁╄祫浜х鐞嗗櫒鍦ㄩ娆℃樉绀烘椂鎵嶅姞杞?
                # 杩欐牱鍙互閬垮厤鍚姩鏃剁殑鍗￠】锛屾彁鍗囩敤鎴蜂綋楠?
                logger.info("涓荤獥鍙ｅ垱寤哄畬鎴愶紝鍑嗗鏄剧ず")
                splash.update_progress(100, "鍚姩瀹屾垚锛?)
                app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

                # 鈿?浼樺寲锛氬欢杩?00ms鍚庡姞杞芥ā鍧椼€佸叧闂惎鍔ㄧ晫闈㈠苟鏄剧ず涓荤獥鍙?
                def load_and_show_window():
                    """鍔犺浇绗竴涓ā鍧楋紝鍏抽棴鍚姩鐣岄潰锛岀劧鍚庢樉绀轰富绐楀彛"""
                    # 鍏堝姞杞界涓€涓ā鍧楋紙璧勪骇搴擄級锛岄伩鍏嶆樉绀哄崰浣嶉〉
                    logger.info("棰勫姞杞界涓€涓ā鍧楋紙璧勪骇搴擄級")
                    
                    def on_assets_loaded():
                        """璧勪骇鍔犺浇瀹屾垚鍥炶皟"""
                        logger.info("璧勪骇鍔犺浇瀹屾垚鍥炶皟琚皟鐢?)
                        # 澶氭澶勭悊浜嬩欢锛岀‘淇漊I鏇存柊
                        for _ in range(3):
                            app.processEvents()  # 璁╄繘搴︽潯鍔ㄧ敾鏇存柊

                        # 鍏抽棴鍚姩鐣岄潰
                        splash.finish()

                        # 鏄剧ず涓荤獥鍙?
                        main_window.show()  # type: ignore
                        main_window.raise_()  # type: ignore
                        main_window.activateWindow()  # type: ignore
                        logger.info("涓荤獥鍙ｅ凡鏄剧ず")
                    
                    # 鍔犺浇妯″潡骞跺紓姝ュ姞杞借祫浜?
                    logger.info("寮€濮嬪姞杞藉垵濮嬫ā鍧?)
                    main_window.load_initial_module(on_complete=on_assets_loaded)  # type: ignore

                QTimer.singleShot(500, load_and_show_window)

                # 鈿?鎬ц兘浼樺寲锛氳褰曠獥鍙ｅ垱寤烘椂闂达紙Requirement 16.5锛?
                window_create_time = time.time()
                startup_duration = window_create_time - startup_start_time
                logger.info(f"鈿?鍚姩鎬ц兘锛氫粠鍚姩鍒扮獥鍙ｅ垱寤鸿€楁椂 {startup_duration:.3f} 绉?)

                if startup_duration < 1.0:
                    logger.info(f"鉁?鍚姩鎬ц兘杈炬爣锛? 1绉掞級")
                else:
                    logger.warning(f"鈿狅笍 鍚姩鎬ц兘鏈揪鏍囷紙鐩爣 < 1绉掞紝瀹為檯 {startup_duration:.3f}绉掞級")

                # 鍚姩鍗曞疄渚嬫湇鍔″櫒
                single_instance.start_server(main_window)

                logger.info("搴旂敤绋嬪簭瀹屽叏鍚姩瀹屾垚")
                
            except Exception as e:
                logger.error(f"鍒涘缓涓荤獥鍙ｆ椂鍙戠敓閿欒: {e}", exc_info=True)
                QMessageBox.critical(
                    None,
                    "鍚姩澶辫触",
                    f"鍒涘缓涓荤獥鍙ｅけ璐? {str(e)}"
                )
                app.quit()
        
        def on_startup_error(error_message: str):
            """鍚姩閿欒鍥炶皟"""
            nonlocal splash
            logger.error(f"鍚姩杩囩▼鍑洪敊: {error_message}")
            splash.close()
            QMessageBox.critical(
                None,
                "鍚姩閿欒",
                f"鍚姩杩囩▼涓彂鐢熼敊璇?\n{error_message}"
            )
            app.quit()

        # 寮傛鍚姩搴旂敤绋嬪簭锛堟棩蹇椾細鑷姩鏇存柊杩涘害鏉★紝涓嶉渶瑕?on_progress 鍥炶皟锛?
        logger.info("寮€濮嬪紓姝ュ惎鍔ㄥ簲鐢ㄧ▼搴?)
        app_manager.start_async(
            on_complete=on_startup_complete,
            on_error=on_startup_error
        )
        
        # 杩愯搴旂敤绋嬪簭浜嬩欢寰幆
        exit_code = app.exec()
        
        # 娓呯悊鍗曞疄渚嬭祫婧?
        single_instance.cleanup()
        
        logger.info(f"搴旂敤绋嬪簭閫€鍑猴紝閫€鍑虹爜: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.error(f"鍚姩搴旂敤绋嬪簭鏃跺彂鐢熼敊璇? {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
