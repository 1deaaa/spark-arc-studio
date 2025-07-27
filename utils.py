import os

def get_user_projects_root(user_id):
    """获取用户所有项目的根目录"""
    return os.path.join('userdata', f'uid_{user_id}', 'projects')

def get_project_path(user_id, project_name):
    """获取用户特定项目的路径"""
    return os.path.join(get_user_projects_root(user_id), project_name)

def ensure_project_directory(user_id, project_name):
    """确保项目目录存在"""
    project_path = get_project_path(user_id, project_name)
    if not os.path.exists(project_path):
        os.makedirs(project_path)
    return project_path