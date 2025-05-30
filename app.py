from flask import Flask, send_from_directory, jsonify
import os
import json

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    """提供主页"""
    return send_from_directory('.', 'index.html')

@app.route('/对话.json')
def get_dialogue_data():
    """获取对话数据，优先从文件读取，文件不存在则返回默认数据"""
    try:
        # 尝试读取文件
        file_path = os.path.join(os.path.dirname(__file__), '对话.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            print("对话.json 文件不存在，返回默认数据")
            return jsonify("")
    except Exception as e:
        print(f"加载对话.json 出错: {e}")
        return jsonify("")

@app.route('/save', methods=['POST'])
def save_dialogue():
    """保存对话数据到文件"""
    from flask import request
    try:
        data = request.json
        with open('对话.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@app.route('/api/json-files')
def get_json_files():
    """获取stories文件夹下所有JSON文件的文件树结构"""
    try:
        def scan_directory(path, relative_path=""):
            """递归扫描目录，构建文件树"""
            items = []
            if not os.path.exists(path):
                return items
                
            for item in sorted(os.listdir(path), key=str.lower):  # 按首字母排序
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path) and item.endswith('.json'):
                    # JSON文件，去掉.json后缀
                    name = item[:-5]  # 去掉.json后缀
                    items.append({
                        'name': name,
                        'type': 'json',
                        'path': os.path.join(relative_path, item) if relative_path else item
                    })
                elif os.path.isdir(item_path) and not item.startswith('.'):
                    # 文件夹
                    children = scan_directory(item_path, os.path.join(relative_path, item) if relative_path else item)
                    items.append({
                        'name': item,
                        'type': 'folder',
                        'children': children
                    })
            return items
        
        # 确保stories文件夹存在
        stories_path = './stories'
        if not os.path.exists(stories_path):
            os.makedirs(stories_path)
        
        # 扫描stories目录，返回其内容（不显示stories文件夹本身）
        file_tree = scan_directory(stories_path)
        return jsonify(file_tree)
    except Exception as e:
        print(f"获取JSON文件列表失败: {e}")
        return jsonify([])

if __name__ == '__main__':
    # 检查对话.json是否存在，不存在则创建默认文件
    if not os.path.exists('对话.json'):
        try:
            with open('对话.json', 'w', encoding='utf-8') as f:
                json.dump("", f, ensure_ascii=False, indent=2)
            print("已创建默认的对话.json文件")
        except Exception as e:
            print(f"创建默认对话.json失败: {e}")
    
    # 启动服务器
    print("服务器启动在 http://127.0.0.1:5000")
    print("请在浏览器中访问此地址来使用对话编辑器")
    app.run(debug=True)