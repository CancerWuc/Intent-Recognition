from .models import db, Scene, Intent, Agent, SceneVector, IntentVector, SessionHistory, MultiAgent, MultiAgentsMapping
import json

def ensure_database_extensions():
    MultiAgentsMapping.__table__.create(bind=db.engine, checkfirst=True)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_database_extensions()

def reset_db(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        ensure_database_extensions()

def load_initial_data(app):
    with app.app_context():
        # 先创建默认的Multi-Agent
        if MultiAgent.query.count() == 0:
            default_multi_agent = MultiAgent()
            default_multi_agent.id = 'default-multi-agent'
            default_multi_agent.name = '默认系统'
            default_multi_agent.description = '默认的多智能体系统'
            default_multi_agent.is_default = True
            default_multi_agent.is_active = True
            db.session.add(default_multi_agent)
            db.session.commit()
            print("已创建默认Multi-Agent")
        
        # 获取默认Multi-Agent ID
        default_ma = MultiAgent.query.filter_by(is_default=True).first()
        default_ma_id = default_ma.id if default_ma else 'default-multi-agent'
        
        if Scene.query.count() == 0:
            scenes_data = [
                {
                    'id': 'stock_query_analysis',
                    'name': '股票查询和分析',
                    'description': '提供股票信息查询和分析服务',
                    'keywords': ['股票', '个股', '指数', '选股', '诊断'],
                    'examples': ['查询贵州茅台的股票信息', '帮我诊断一下五粮液的股票']
                },
                {
                    'id': 'fund_query_analysis',
                    'name': '基金查询和分析',
                    'description': '提供基金信息查询和分析服务',
                    'keywords': ['基金', '公募', 'ETF', '基金经理', '选基'],
                    'examples': ['查询华夏成长混合基金的信息', '分析易方达消费行业基金']
                },
                {
                    'id': 'customer_service',
                    'name': '客服',
                    'description': '提供客服相关服务',
                    'keywords': ['客服', 'FAQ', '业务办理', '人工'],
                    'examples': ['如何开户', '我要办理开户', '转人工客服']
                },
                {
                    'id': 'general',
                    'name': '通用',
                    'description': '提供通用闲聊服务',
                    'keywords': ['闲聊', '聊天', '你好'],
                    'examples': ['你好', '今天天气怎么样', '陪我聊聊天']
                }
            ]
            
            for scene_data in scenes_data:
                scene = Scene()
                scene.from_dict(scene_data)
                scene.multi_agent_id = default_ma_id  # 关联到默认Multi-Agent
                db.session.add(scene)
            
            db.session.commit()
            print(f"已初始化 {len(scenes_data)} 个场景")
        
        if Agent.query.count() == 0:
            agents_data = [
                {
                    'id': 'stock_info_query_agent',
                    'name': '个股信息查询Agent',
                    'description': '查询个股基本信息',
                    'prompt': '你是一个股票信息查询助手，需要根据用户输入提供准确的个股信息，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['个股信息查询', '基本数据获取'],
                    'parameters': {}
                },
                {
                    'id': 'stock_diagnosis_agent',
                    'name': '个股诊断Agent',
                    'description': '对个股进行综合诊断',
                    'prompt': '你是一个股票诊断助手，需要根据用户输入提供准确的个股诊断报告，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['个股诊断', '投资建议'],
                    'parameters': {}
                },
                {
                    'id': 'index_analysis_agent',
                    'name': '指数分析Agent',
                    'description': '分析指数走势和成分',
                    'prompt': '你是一个指数分析助手，需要根据用户输入提供准确的指数分析报告，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['指数分析', '走势预测'],
                    'parameters': {}
                },
                {
                    'id': 'multi_stock_comparison_agent',
                    'name': '多股对比Agent',
                    'description': '对比多个股票或指数的表现',
                    'prompt': '你是一个多股对比助手，需要根据用户输入提供准确的多股对比分析，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['多股对比', '数据可视化'],
                    'parameters': {}
                },
                {
                    'id': 'stock_selection_agent',
                    'name': '综合选股Agent',
                    'description': '基于多种指标进行综合选股',
                    'prompt': '你是一个综合选股助手，需要根据用户输入提供准确的选股建议，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['综合选股', '投资组合建议'],
                    'parameters': {}
                },
                {
                    'id': 'fund_info_query_agent',
                    'name': '公募基金信息查询Agent',
                    'description': '查询公募基金基本信息',
                    'prompt': '你是一个基金信息查询助手，需要根据用户输入提供准确的基金信息，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['基金信息查询', '基本数据获取'],
                    'parameters': {}
                },
                {
                    'id': 'fund_analysis_agent',
                    'name': '公募基金分析Agent',
                    'description': '分析公募基金表现',
                    'prompt': '你是一个基金分析助手，需要根据用户输入提供准确的基金分析报告，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['基金分析', '风险评估'],
                    'parameters': {}
                },
                {
                    'id': 'etf_info_query_agent',
                    'name': '场内ETF信息查询Agent',
                    'description': '查询场内ETF基本信息',
                    'prompt': '你是一个ETF信息查询助手，需要根据用户输入提供准确的ETF信息，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['ETF信息查询', '基本数据获取'],
                    'parameters': {}
                },
                {
                    'id': 'etf_analysis_agent',
                    'name': '场内ETF分析Agent',
                    'description': '分析场内ETF表现',
                    'prompt': '你是一个ETF分析助手，需要根据用户输入提供准确的ETF分析报告，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['ETF分析', '跟踪误差评估'],
                    'parameters': {}
                },
                {
                    'id': 'fund_manager_info_query_agent',
                    'name': '基金经理信息查询Agent',
                    'description': '查询基金经理基本信息',
                    'prompt': '你是一个基金经理信息查询助手，需要根据用户输入提供准确的基金经理信息，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['基金经理信息查询', '从业经历'],
                    'parameters': {}
                },
                {
                    'id': 'fund_manager_analysis_agent',
                    'name': '基金经理信息分析Agent',
                    'description': '分析基金经理投资风格和业绩',
                    'prompt': '你是一个基金经理分析助手，需要根据用户输入提供准确的基金经理分析报告，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['基金经理分析', '投资风格评估'],
                    'parameters': {}
                },
                {
                    'id': 'multi_fund_comparison_agent',
                    'name': '多基金对比Agent',
                    'description': '对比多个基金的表现',
                    'prompt': '你是一个多基金对比助手，需要根据用户输入提供准确的多基金对比分析，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['多基金对比', '数据可视化'],
                    'parameters': {}
                },
                {
                    'id': 'fund_selection_agent',
                    'name': '综合选基Agent',
                    'description': '基于多种指标进行综合选基',
                    'prompt': '你是一个综合选基助手，需要根据用户输入提供准确的选基建议，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['综合选基', '投资组合建议'],
                    'parameters': {}
                },
                {
                    'id': 'fund_manager_selection_agent',
                    'name': '选基金经理Agent',
                    'description': '基于业绩和风格选择基金经理',
                    'prompt': '你是一个基金经理选择助手，需要根据用户输入提供准确的基金经理选择建议，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['基金经理选择', '风格匹配'],
                    'parameters': {}
                },
                {
                    'id': 'customer_service_faq_agent',
                    'name': '客服FAQ Agent',
                    'description': '回答常见问题',
                    'prompt': '你是一个客服FAQ助手，需要根据用户输入提供准确的问题解答，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['常见问题解答', '政策咨询'],
                    'parameters': {}
                },
                {
                    'id': 'business_processing_agent',
                    'name': '业务办理Agent',
                    'description': '办理各种业务',
                    'prompt': '你是一个业务办理助手，需要根据用户输入提供准确的业务办理信息，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['业务办理', '流程指导'],
                    'parameters': {}
                },
                {
                    'id': 'transfer_to_human_agent',
                    'name': '转人工Agent',
                    'description': '转接到人工客服',
                    'prompt': '你是一个转人工客服助手，需要根据用户输入提供准确的转人工客服信息，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['转人工服务', '紧急处理'],
                    'parameters': {}
                },
                {
                    'id': 'chat_companion_agent',
                    'name': '闲聊陪伴Agent',
                    'description': '提供闲聊陪伴服务',
                    'prompt': '你是一个闲聊陪伴助手，需要根据用户输入提供友好、自然的回应，用自然语言回复，不需要JSON格式。',
                    'capabilities': ['闲聊对话', '情感陪伴'],
                    'parameters': {}
                }
            ]
            
            for agent_data in agents_data:
                agent = Agent()
                agent.from_dict(agent_data)
                db.session.add(agent)
            
            db.session.commit()
            print(f"已初始化 {len(agents_data)} 个智能体")
        
        if Intent.query.count() == 0:
            intents_data = [
                {
                    'id': 'individual_stock_info_query',
                    'scene_id': 'stock_query_analysis',
                    'name': '个股-信息查询',
                    'description': '查询个股基本信息',
                    'keywords': ['股票信息', '个股信息', '查询股票'],
                    'examples': ['查询贵州茅台的股票信息'],
                    'agent_id': 'stock_info_query_agent'
                },
                {
                    'id': 'individual_stock_diagnosis',
                    'scene_id': 'stock_query_analysis',
                    'name': '个股-个股诊断',
                    'description': '对个股进行综合诊断',
                    'keywords': ['诊断', '股票诊断', '个股诊断'],
                    'examples': ['帮我诊断一下五粮液的股票'],
                    'agent_id': 'stock_diagnosis_agent'
                },
                {
                    'id': 'index_analysis',
                    'scene_id': 'stock_query_analysis',
                    'name': '指数-指数分析',
                    'description': '分析指数走势和成分',
                    'keywords': ['指数', '指数分析', '走势分析'],
                    'examples': ['分析一下上证指数的走势'],
                    'agent_id': 'index_analysis_agent'
                },
                {
                    'id': 'multi_stock_comparison',
                    'scene_id': 'stock_query_analysis',
                    'name': '个股或指数-多股对比',
                    'description': '对比多个股票或指数的表现',
                    'keywords': ['对比', '多股对比', '股票对比'],
                    'examples': ['对比贵州茅台和五粮液'],
                    'agent_id': 'multi_stock_comparison_agent'
                },
                {
                    'id': 'comprehensive_stock_selection',
                    'scene_id': 'stock_query_analysis',
                    'name': '选股-综合选股',
                    'description': '基于多种指标进行综合选股',
                    'keywords': ['选股', '推荐股票', '综合选股'],
                    'examples': ['推荐几只好股票'],
                    'agent_id': 'stock_selection_agent'
                },
                {
                    'id': 'public_fund_info_query',
                    'scene_id': 'fund_query_analysis',
                    'name': '个基-公募基金信息查询',
                    'description': '查询公募基金基本信息',
                    'keywords': ['基金信息', '公募基金', '查询基金'],
                    'examples': ['查询华夏成长混合基金的信息'],
                    'agent_id': 'fund_info_query_agent'
                },
                {
                    'id': 'public_fund_analysis',
                    'scene_id': 'fund_query_analysis',
                    'name': '个基-公募基金分析',
                    'description': '分析公募基金表现',
                    'keywords': ['基金分析', '公募基金分析'],
                    'examples': ['分析易方达消费行业基金'],
                    'agent_id': 'fund_analysis_agent'
                },
                {
                    'id': 'etf_info_query',
                    'scene_id': 'fund_query_analysis',
                    'name': '个基-场内ETF信息查询',
                    'description': '查询场内ETF基本信息',
                    'keywords': ['ETF信息', '场内ETF', '查询ETF'],
                    'examples': ['查询沪深300ETF的信息'],
                    'agent_id': 'etf_info_query_agent'
                },
                {
                    'id': 'etf_analysis',
                    'scene_id': 'fund_query_analysis',
                    'name': '个基-场内ETF分析',
                    'description': '分析场内ETF表现',
                    'keywords': ['ETF分析', '场内ETF分析'],
                    'examples': ['分析沪深300ETF的表现'],
                    'agent_id': 'etf_analysis_agent'
                },
                {
                    'id': 'fund_manager_info_query',
                    'scene_id': 'fund_query_analysis',
                    'name': '基金经理-信息查询',
                    'description': '查询基金经理基本信息',
                    'keywords': ['基金经理', '基金经理信息'],
                    'examples': ['查询张坤的信息'],
                    'agent_id': 'fund_manager_info_query_agent'
                },
                {
                    'id': 'fund_manager_info_analysis',
                    'scene_id': 'fund_query_analysis',
                    'name': '基金经理-信息分析',
                    'description': '分析基金经理投资风格和业绩',
                    'keywords': ['基金经理分析', '投资风格'],
                    'examples': ['分析张坤的投资风格'],
                    'agent_id': 'fund_manager_analysis_agent'
                },
                {
                    'id': 'multi_fund_comparison',
                    'scene_id': 'fund_query_analysis',
                    'name': '基金诊断-多基金对比',
                    'description': '对比多个基金的表现',
                    'keywords': ['基金对比', '多基金对比'],
                    'examples': ['对比华夏成长和易方达消费行业'],
                    'agent_id': 'multi_fund_comparison_agent'
                },
                {
                    'id': 'comprehensive_fund_selection',
                    'scene_id': 'fund_query_analysis',
                    'name': '选基-综合选基',
                    'description': '基于多种指标进行综合选基',
                    'keywords': ['选基', '推荐基金', '综合选基'],
                    'examples': ['推荐几只好基金'],
                    'agent_id': 'fund_selection_agent'
                },
                {
                    'id': 'fund_manager_selection',
                    'scene_id': 'fund_query_analysis',
                    'name': '选基-选基金经理',
                    'description': '基于业绩和风格选择基金经理',
                    'keywords': ['选基金经理', '推荐基金经理'],
                    'examples': ['推荐几个优秀的基金经理'],
                    'agent_id': 'fund_manager_selection_agent'
                },
                {
                    'id': 'customer_service_faq',
                    'scene_id': 'customer_service',
                    'name': '客服-客服FAQ',
                    'description': '回答常见问题',
                    'keywords': ['FAQ', '常见问题', '问题'],
                    'examples': ['如何开户'],
                    'agent_id': 'customer_service_faq_agent'
                },
                {
                    'id': 'business_processing',
                    'scene_id': 'customer_service',
                    'name': '客服-业务办理',
                    'description': '办理各种业务',
                    'keywords': ['业务办理', '办理', '开户'],
                    'examples': ['我要办理开户'],
                    'agent_id': 'business_processing_agent'
                },
                {
                    'id': 'transfer_to_human',
                    'scene_id': 'customer_service',
                    'name': '客服-转人工',
                    'description': '转接到人工客服',
                    'keywords': ['转人工', '人工客服', '客服'],
                    'examples': ['转人工客服'],
                    'agent_id': 'transfer_to_human_agent'
                },
                {
                    'id': 'chat_companion',
                    'scene_id': 'general',
                    'name': '闲聊-闲聊陪伴',
                    'description': '提供闲聊陪伴服务',
                    'keywords': ['闲聊', '聊天', '你好'],
                    'examples': ['你好', '陪我聊聊天'],
                    'agent_id': 'chat_companion_agent'
                }
            ]
            
            for intent_data in intents_data:
                intent = Intent()
                intent.from_dict(intent_data)
                db.session.add(intent)
            
            db.session.commit()
            print(f"已初始化 {len(intents_data)} 个意图")
