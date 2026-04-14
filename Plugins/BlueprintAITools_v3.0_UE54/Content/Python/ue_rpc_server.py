# -*- coding: utf-8 -*-

"""
UE RPC 服务器（简化版 - 只读模式）

只支持读取操作，不支持修改蓝图
确保 100% 稳定，不会崩溃
"""

import socket
import struct
import json
import threading
import traceback
import unreal
import blueprint_tools

# --- 配置 ---
HOST = '127.0.0.1'
PORT = 9998

def _recv_exact(conn, length):
    """精确接收指定长度的数据"""
    buffers = []
    bytes_received = 0
    while bytes_received < length:
        data = conn.recv(length - bytes_received)
        if not data:
            raise ConnectionError("Socket connection broken")
        buffers.append(data)
        bytes_received += len(data)
    return b''.join(buffers)

def _send_message(conn, data_dict):
    """将字典打包成 JSON，并使用 4 字节前缀发送"""
    try:
        msg_json = json.dumps(data_dict, ensure_ascii=False).encode('utf-8')
        prefix = struct.pack('!I', len(msg_json))
        conn.sendall(prefix + msg_json)
    except Exception as e:
        unreal.log_error("[UERPCServer] 发送消息失败: {}".format(e))

def _handle_request(conn):
    """处理单个客户端请求（只读模式）"""
    try:
        # 1. 读取请求
        prefix_data = _recv_exact(conn, 4)
        msg_length = struct.unpack('!I', prefix_data)[0]
        msg_data = _recv_exact(conn, msg_length)
        request = json.loads(msg_data.decode('utf-8'))
        
        action = request.get('action')
        parameters = request.get('parameters', {})
        
        unreal.log("[UERPCServer] 收到请求: {}".format(action))

        response = {}

        # 2. 只处理读取操作（安全，不会崩溃）
        try:
            if action == "get_current_blueprint_summary":
                # 读取蓝图
                bp = unreal.BlueprintAIToolsLibrary.get_current_open_blueprint()
                if bp:
                    json_str = unreal.BlueprintAIToolsLibrary.export_blueprint_summary(bp, True)
                    result_data = json.loads(json_str)
                    response = {"status": "success", "data": result_data}
                else:
                    response = {"status": "error", "message": "未找到打开的蓝图"}
            
            elif action == "query_available_nodes":
                # 查询节点字典（支持按需查询：分类、单节点）
                category = parameters.get('category', '')
                node_name = parameters.get('node_name', '')
                result_json_str = blueprint_tools.query_available_nodes(category, node_name)
                result_data = json.loads(result_json_str)
                response = {"status": "success", "data": result_data}
            
            elif action == "validate_blueprint":
                # 验证蓝图
                bp = unreal.BlueprintAIToolsLibrary.get_current_open_blueprint()
                if bp:
                    json_str = unreal.BlueprintAIToolsLibrary.validate_blueprint(bp)
                    result_data = json.loads(json_str)
                    response = {"status": "success", "data": result_data}
                else:
                    response = {"status": "error", "message": "未找到打开的蓝图"}
            
            elif action == "get_selected_nodes":
                # 获取选中的节点（实验性）
                result_json_str = blueprint_tools.get_selected_nodes()
                result_data = json.loads(result_json_str)
                response = {"status": "success", "data": result_data}
            
            elif action == "apply_blueprint_changes":
                # 修改功能已禁用
                response = {
                    "status": "error",
                    "message": "蓝图修改功能暂时不可用。当前版本只支持分析和验证蓝图。"
                }
            
            elif action == "ping":
                response = {"status": "success", "message": "pong"}
            
            else:
                response = {"status": "error", "message": "未知的操作: {}".format(action)}

        except Exception as e:
            unreal.log_error("[UERPCServer] 工具执行失败: {}".format(e))
            response = {
                "status": "error",
                "message": "执行失败: {}".format(str(e)),
                "traceback": traceback.format_exc()
            }
        
        # 3. 返回结果
        _send_message(conn, response)
        unreal.log("[UERPCServer] 请求完成: {}".format(action))

    except ConnectionError as e:
        unreal.log_warning("[UERPCServer] 客户端连接断开: {}".format(e))
    except Exception as e:
        unreal.log_error("[UERPCServer] 处理请求时发生错误: {}".format(e))
        unreal.log_error(traceback.format_exc())
    finally:
        conn.close()
        unreal.log("[UERPCServer] 连接已关闭")

def _server_thread_func():
    """后台线程中运行的主服务器循环"""
    server_socket = None
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        
        unreal.log_warning("=== UE RPC 服务器已启动（只读模式）===")
        unreal.log_warning("=== 监听地址: {}:{} ===".format(HOST, PORT))
        unreal.log_warning("=== 支持操作：读取蓝图、验证错误、查询节点、获取选中节点 ===")

        while True:
            conn, addr = server_socket.accept()
            unreal.log("[UERPCServer] 接受连接: {}".format(addr))
            
            # 为每个客户端创建处理线程
            client_handler = threading.Thread(target=_handle_request, args=(conn,), daemon=True)
            client_handler.start()

    except Exception as e:
        unreal.log_error("[UERPCServer] 服务器崩溃: {}".format(e))
        unreal.log_error(traceback.format_exc())
    finally:
        if server_socket:
            server_socket.close()
            unreal.log_error("[UERPCServer] 服务器已关闭")

# --- 启动器 ---
_server_thread = None

def start_rpc_server():
    """启动 RPC 服务器（如果尚未运行）"""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        unreal.log_warning("[UERPCServer] 服务器已经在运行中")
        return

    _server_thread = threading.Thread(target=_server_thread_func, daemon=True)
    _server_thread.start()
    unreal.log_warning("[UERPCServer] 服务器线程已启动（只读模式）")

# --- 入口点 ---
if __name__ == "__main__":
    start_rpc_server()
