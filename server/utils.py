import os
import json
def get_character_bind_file_path(character_settings_dir):
    """获取角色绑定文件路径"""
    return os.path.join(character_settings_dir, 'chr.bind')

def load_character_bindings(character_settings_dir):
    """加载所有角色的绑定数据"""
    bind_file_path = get_character_bind_file_path(character_settings_dir)
    if not os.path.exists(bind_file_path):
        return {}
    
    try:
        with open(bind_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, Exception):
        return {}

def save_character_bindings(character_settings_dir, bindings):
    """保存所有角色的绑定数据"""
    bind_file_path = get_character_bind_file_path(character_settings_dir)
    with open(bind_file_path, 'w', encoding='utf-8') as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)
 
def get_user_projects_root(user_id):
    """获取用户所有项目的根目录"""
    return os.path.join('userdata', f'uid_{user_id}', 'projects')

def get_project_path(user_id, project_name):
    """获取用户特定项目的路径"""
    return os.path.join(get_user_projects_root(user_id), project_name)

def get_project_worldview_path(user_id, project_name):
    """获取用户特定项目的世界观文件路径"""
    return os.path.join(get_project_path(user_id, project_name), '世界观.txt')

def get_project_lorebook_path(user_id, project_name, file_name):
    """获取用户特定项目的世界观文件路径"""
    return os.path.join(get_project_path(user_id, project_name), file_name)

def get_worldview_file_path(project_name):
    """获取项目的世界观文件路径（用于settings_routes.py）"""
    # 由于这个函数在settings_routes.py中被调用，而settings_routes.py没有用户ID，
    # 我们需要遍历所有用户目录来查找项目
    userdata_root = 'userdata'
    if not os.path.exists(userdata_root):
        return None
    
    for user_dir in os.listdir(userdata_root):
        if user_dir.startswith('uid_'):
            user_id = user_dir[4:]  # 提取用户ID
            project_path = get_project_path(user_id, project_name)
            if os.path.exists(project_path):
                return os.path.join(project_path, '世界观.txt')
    
    return None

def get_character_settings_dir(project_name):
    """获取项目的角色设定目录路径（用于settings_routes.py）"""
    # 由于这个函数在settings_routes.py中被调用，而settings_routes.py没有用户ID，
    # 我们需要遍历所有用户目录来查找项目
    userdata_root = 'userdata'
    if not os.path.exists(userdata_root):
        return None
    
    for user_dir in os.listdir(userdata_root):
        if user_dir.startswith('uid_'):
            user_id = user_dir[4:]  # 提取用户ID
            project_path = get_project_path(user_id, project_name)
            if os.path.exists(project_path):
                return os.path.join(project_path, 'chr')
    
    return None

def get_project_characters_path(user_id, project_name):
    """获取用户特定项目的角色设定目录路径"""
    return os.path.join(get_project_path(user_id, project_name), 'chr')

def get_project_stories_path(user_id, project_name):
    """获取用户特定项目的stories目录路径"""
    return os.path.join(get_project_path(user_id, project_name), 'stories')

def ensure_project_directory(user_id, project_name):
    """确保项目目录存在"""
    project_path = get_project_path(user_id, project_name)
    if not os.path.exists(project_path):
        os.makedirs(project_path)
    return project_path

def ensure_project_worldview_file(user_id, project_name):
    """确保项目的世界观文件存在"""
    worldview_path = get_project_worldview_path(user_id, project_name)
    if not os.path.exists(worldview_path):
        # 创建默认的世界观文件
        with open(worldview_path, 'w', encoding='utf-8') as f:
            f.write("# 世界观设定\n\n在这里描述你的故事世界...")
    return worldview_path

def ensure_project_characters_directory(user_id, project_name):
    """确保项目的角色设定目录存在"""
    characters_path = get_project_characters_path(user_id, project_name)
    if not os.path.exists(characters_path):
        os.makedirs(characters_path)
        # 创建默认角色
        default_character_id = 0
        default_character_name = "默认角色"
        
        # 创建 .txt 文件
        txt_filename = f"chr_{default_character_id}_设定.txt"
        txt_file_path = os.path.join(characters_path, txt_filename)
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# {default_character_name}\n\n这是默认创建的角色。")
            
        # 更新 chr.bind 文件
        bindings = load_character_bindings(characters_path)
        bindings[str(default_character_id)] = default_character_name
        save_character_bindings(characters_path, bindings)
        
    return characters_path

def ensure_project_stories_directory(user_id, project_name):
    """确保项目的stories目录存在"""
    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        os.makedirs(stories_path)
    return stories_path

def ensure_project_worldview_and_character_settings(user_id: str, project_name: str) -> None:
    """
    确保用户特定项目的世界观文件和角色设定目录存在
    :param user_id: 用户ID
    :param project_name: 项目名称
    """
    # 直接使用传入的 user_id 创建项目目录结构
    ensure_project_directory(user_id, project_name)
    ensure_project_worldview_file(user_id, project_name)
    ensure_project_characters_directory(user_id, project_name)