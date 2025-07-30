import os

def get_user_projects_root(user_id):
    """获取用户所有项目的根目录"""
    return os.path.join('userdata', f'uid_{user_id}', 'projects')

def get_project_path(user_id, project_name):
    """获取用户特定项目的路径"""
    return os.path.join(get_user_projects_root(user_id), project_name)

def get_project_worldview_path(user_id, project_name):
    """获取用户特定项目的世界观文件路径"""
    return os.path.join(get_project_path(user_id, project_name), '世界观.txt')

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
    return characters_path

def ensure_project_stories_directory(user_id, project_name):
    """确保项目的stories目录存在"""
    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        os.makedirs(stories_path)
    return stories_path

def ensure_project_worldview_and_character_settings(project_name: str) -> None:
    """
    确保项目的世界观文件和角色设定目录存在
    :param project_name: 项目名称
    """
    # 由于这个函数在settings_routes.py中被调用，而settings_routes.py没有用户ID，
    # 我们需要遍历所有用户目录来查找项目
    userdata_root = 'userdata'
    if not os.path.exists(userdata_root):
        return
    
    for user_dir in os.listdir(userdata_root):
        if user_dir.startswith('uid_'):
            user_id = user_dir[4:]  # 提取用户ID
            project_path = get_project_path(user_id, project_name)
            if os.path.exists(project_path):
                # 项目存在，确保世界观文件和角色设定目录存在
                ensure_project_worldview_file(user_id, project_name)
                ensure_project_characters_directory(user_id, project_name)
                return
    
    # 如果没有找到项目，创建默认的用户目录和项目
    # 这里我们假设用户ID为'1'，在实际应用中可能需要更复杂的逻辑
    default_user_id = '1'
    ensure_project_directory(default_user_id, project_name)
    ensure_project_worldview_file(default_user_id, project_name)
    ensure_project_characters_directory(default_user_id, project_name)