"""
测试服务器 - 为 HTML 测试运行器提供后端支持
"""
import sys
from pathlib import Path
import json
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestServerHandler(SimpleHTTPRequestHandler):
    """测试服务器处理器"""
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/run_test':
            # 运行测试
            query = parse_qs(parsed_path.query)
            test_file = query.get('test_file', [''])[0]
            
            if test_file:
                result = self.run_test(test_file)
                self.send_json_response(result)
            else:
                self.send_json_response({'error': 'No test file specified'}, 400)
        else:
            # 默认处理静态文件
            super().do_GET()
    
    def run_test(self, test_file: str) -> dict:
        """运行单个测试"""
        tests_dir = PROJECT_ROOT / 'tests'
        test_path = tests_dir / test_file
        
        if not test_path.exists():
            return {
                'passed': False,
                'duration': 0,
                'error': f'Test file not found: {test_file}'
            }
        
        try:
            # 运行 pytest
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', str(test_path), '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(PROJECT_ROOT)
            )
            
            passed = result.returncode == 0
            error = None if passed else result.stdout + '\n' + result.stderr
            
            # 提取运行时间（简单解析）
            duration = 0.0
            for line in result.stdout.split('\n'):
                if 'passed' in line or 'failed' in line:
                    try:
                        # 尝试提取时间
                        if 's' in line:
                            parts = line.split()
                            for part in parts:
                                if part.endswith('s'):
                                    duration = float(part[:-1])
                                    break
                    except:
                        pass
            
            return {
                'passed': passed,
                'duration': f'{duration:.2f}',
                'error': error
            }
            
        except subprocess.TimeoutExpired:
            return {
                'passed': False,
                'duration': 60.0,
                'error': 'Test timeout after 60 seconds'
            }
        except Exception as e:
            return {
                'passed': False,
                'duration': 0,
                'error': str(e)
            }
    
    def send_json_response(self, data: dict, status_code: int = 200):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def start_server(port: int = 8000):
    """启动测试服务器"""
    # 切换到 tools 目录，这样可以直接访问 test_runner.html
    import os
    os.chdir(PROJECT_ROOT / 'tools')
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, TestServerHandler)
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   🧪 测试运行器服务器已启动                              ║
║                                                          ║
║   📡 服务器地址: http://localhost:{port}                  ║
║   📄 测试界面: http://localhost:{port}/test_runner.html   ║
║                                                          ║
║   💡 在浏览器中打开上面的地址即可使用测试运行器！         ║
║                                                          ║
║   按 Ctrl+C 停止服务器                                   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
        httpd.shutdown()


if __name__ == '__main__':
    start_server()

