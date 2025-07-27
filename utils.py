import os

def get_user_stories_path(user_id):
    """获取用户专属的stories路径"""
    return os.path.join('userdata', f'uid_{user_id}', 'stories')

def ensure_user_directory(user_id):
    """确保用户目录存在"""
    user_path = os.path.join('userdata', f'uid_{user_id}')
    stories_path = get_user_stories_path(user_id)
    
    if not os.path.exists(user_path):
        os.makedirs(user_path)
    
    if not os.path.exists(stories_path):
        os.makedirs(stories_path)
    
    return stories_path