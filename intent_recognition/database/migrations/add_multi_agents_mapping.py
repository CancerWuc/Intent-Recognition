from intent_recognition.database import db
from intent_recognition.database.models import MultiAgentsMapping


def upgrade():
    """升级数据库：添加multi_agents_mapping表"""
    MultiAgentsMapping.__table__.create(bind=db.engine, checkfirst=True)
    print("数据库升级完成：multi_agents_mapping表已添加")


def downgrade():
    """回滚：移除multi_agents_mapping表"""
    MultiAgentsMapping.__table__.drop(bind=db.engine, checkfirst=True)
    print("数据库回滚完成：multi_agents_mapping表已移除")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
            downgrade()
        else:
            upgrade()
