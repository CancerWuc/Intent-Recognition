from ...database import db
from datetime import datetime
import json


def upgrade():
    """升级数据库：添加Multi-Agent支持"""
    
    # 1. 创建multi_agents表
    db.engine.execute('''
        CREATE TABLE IF NOT EXISTS multi_agents (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            icon VARCHAR(50),
            color VARCHAR(20),
            is_default BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )
    ''')
    
    # 2. 修改scenes表，添加multi_agent_id外键（先允许NULL，以便后续填充数据）
    try:
        db.engine.execute('''
            ALTER TABLE scenes 
            ADD COLUMN multi_agent_id VARCHAR(50)
        ''')
    except Exception as e:
        print(f"添加multi_agent_id列可能已存在: {e}")
    
    # 3. 创建默认Multi-Agent
    from sqlalchemy import text
    default_ma_id = 'default-multi-agent'
    try:
        result = db.engine.execute(text(f'''
            INSERT INTO multi_agents (id, name, description, is_default, created_at, updated_at)
            VALUES ('{default_ma_id}', '默认系统', '默认的多智能体系统', 1, datetime('now'), datetime('now'))
        '''))
        print(f"创建默认Multi-Agent: {default_ma_id}")
    except Exception as e:
        print(f"默认Multi-Agent可能已存在: {e}")
    
    # 4. 将现有场景关联到默认Multi-Agent
    try:
        db.engine.execute(text(f'''
            UPDATE scenes SET multi_agent_id = '{default_ma_id}' WHERE multi_agent_id IS NULL
        '''))
        print("将现有场景关联到默认Multi-Agent")
    except Exception as e:
        print(f"关联场景到默认Multi-Agent失败: {e}")
    
    # 5. 添加外键约束
    try:
        db.engine.execute('''
            ALTER TABLE scenes 
            ADD CONSTRAINT fk_scenes_multi_agent 
            FOREIGN KEY (multi_agent_id) REFERENCES multi_agents(id)
        ''')
        print("添加外键约束: fk_scenes_multi_agent")
    except Exception as e:
        print(f"外键约束可能已存在: {e}")
    
    # 6. 添加sort_order列（如果不存在）
    try:
        db.engine.execute('''
            ALTER TABLE scenes 
            ADD COLUMN sort_order INTEGER DEFAULT 0
        ''')
        print("添加sort_order列")
    except Exception as e:
        print(f"sort_order列可能已存在: {e}")
    
    print("数据库升级完成：Multi-Agent支持已添加")


def downgrade():
    """回滚：移除Multi-Agent支持"""
    
    # 1. 移除外键约束
    try:
        db.engine.execute('''
            ALTER TABLE scenes DROP CONSTRAINT fk_scenes_multi_agent
        ''')
        print("移除外键约束")
    except Exception as e:
        print(f"外键约束可能不存在: {e}")
    
    # 2. 移除multi_agent_id列
    try:
        db.engine.execute('''
            ALTER TABLE scenes DROP COLUMN multi_agent_id
        ''')
        print("移除multi_agent_id列")
    except Exception as e:
        print(f"multi_agent_id列可能不存在: {e}")
    
    # 3. 移除sort_order列
    try:
        db.engine.execute('''
            ALTER TABLE scenes DROP COLUMN sort_order
        ''')
        print("移除sort_order列")
    except Exception as e:
        print(f"sort_order列可能不存在: {e}")
    
    # 4. 删除multi_agents表
    try:
        db.engine.execute('''
            DROP TABLE IF EXISTS multi_agents
        ''')
        print("删除multi_agents表")
    except Exception as e:
        print(f"multi_agents表可能不存在: {e}")
    
    print("数据库回滚完成：Multi-Agent支持已移除")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
            downgrade()
        else:
            upgrade()
