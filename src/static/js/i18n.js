/**
 * News Agent i18n - English / Chinese language switching
 */
(function (global) {
    const STORAGE_KEY = 'newsagent_lang';

    const translations = {
        en: {
            app_name: 'News Agent',
            nav_dashboard: 'Dashboard',
            nav_articles: 'Articles',
            nav_sources: 'Sources',
            nav_activity: 'Recent Activity',
            lang_switch: '中文',
            page_dashboard: 'Dashboard',
            page_articles: 'Articles',
            page_sources: 'Sources',
            total_articles: 'Total Articles',
            active_sources: 'Active Sources',
            last_collection: 'Last Collection',
            success_rate: 'Success Rate',
            ai_news_title: 'AI News Intelligence',
            ai_news_desc: 'Track the latest developments in Artificial Intelligence, Machine Learning, and emerging AI technologies.',
            ai_articles: 'AI Articles',
            of_total: 'of Total',
            view_ai_news: 'View AI News',
            service_control: 'Service Control',
            service_controls: 'Service Controls',
            initialize: 'Initialize',
            start: 'Start',
            stop: 'Stop',
            recent_activity: 'Recent Activity',
            service_logs: 'Service Logs',
            refresh: 'Refresh',
            close: 'Close',
            loading_activity: 'Loading activity...',
            loading_logs: 'Loading logs...',
            service_status: 'Service Status',
            running: 'Running',
            stopped: 'Stopped',
            idle: 'Idle',
            no_collectors: 'No active collectors',
            no_activity: 'No activity data available',
            failed_activity: 'Failed to load activity',
            init_success: 'Service initialized successfully!',
            start_success: 'Service started successfully!',
            stop_success: 'Service stopped successfully!',
            search_articles: 'Search Articles',
            collect_now: 'Collect Now',
            filter_sentiment: 'Filter by Sentiment',
            all: 'All',
            positive: 'Positive',
            negative: 'Negative',
            neutral: 'Neutral',
            mixed: 'Mixed',
            source_name: 'Source Name',
            source_url: 'Source URL',
            source_type: 'Type',
            status: 'Status',
            articles_count: 'Articles',
            actions: 'Actions',
            add_source: 'Add Source',
            test_source: 'Test',
            edit_source: 'Edit',
            delete_source: 'Delete',
            save: 'Save',
            cancel: 'Cancel',
            active: 'Active',
            inactive: 'Inactive',
            never: 'Never',
            last: 'Last',
            articles_label: 'Articles',
            no_articles: 'No articles found',
            load_more: 'Load More',
            published: 'Published',
            collected: 'Collected',
            sentiment: 'Sentiment',
            category: 'Category',
            read_more: 'Read More',
            fill_required: 'Please fill in required fields',
            add_success: 'Source added successfully!',
            add_failed: 'Add failed:',
            update_success: 'Source updated successfully!',
            update_failed: 'Update failed:',
            delete_success: 'Source deleted successfully!',
            delete_failed: 'Delete failed:',
            test_success: 'Test successful:',
            error_generic: 'An error occurred:',
        },
        zh: {
            app_name: '新闻智能体',
            nav_dashboard: '仪表盘',
            nav_articles: '文章',
            nav_sources: '新闻源',
            nav_activity: '最近活动',
            lang_switch: 'EN',
            page_dashboard: '仪表盘',
            page_articles: '文章列表',
            page_sources: '新闻源管理',
            total_articles: '文章总数',
            active_sources: '活跃来源',
            last_collection: '最近采集',
            success_rate: '成功率',
            ai_news_title: 'AI 新闻智能',
            ai_news_desc: '追踪人工智能、机器学习与前沿 AI 技术的最新动态。',
            ai_articles: 'AI 文章',
            of_total: '占总比',
            view_ai_news: '查看 AI 新闻',
            service_control: '服务控制',
            service_controls: '服务控制',
            initialize: '初始化',
            start: '启动',
            stop: '停止',
            recent_activity: '最近活动',
            service_logs: '服务日志',
            refresh: '刷新',
            close: '关闭',
            loading_activity: '正在加载活动...',
            loading_logs: '正在加载日志...',
            service_status: '服务状态',
            running: '运行中',
            stopped: '已停止',
            idle: '空闲',
            no_collectors: '暂无活跃采集器',
            no_activity: '暂无活动数据',
            failed_activity: '加载活动失败',
            init_success: '服务初始化成功！',
            start_success: '服务启动成功！',
            stop_success: '服务停止成功！',
            search_articles: '搜索文章',
            collect_now: '立即采集',
            filter_sentiment: '按情感筛选',
            all: '全部',
            positive: '积极',
            negative: '消极',
            neutral: '中性',
            mixed: '混合',
            source_name: '来源名称',
            source_url: '来源地址',
            source_type: '类型',
            status: '状态',
            articles_count: '文章数',
            actions: '操作',
            add_source: '添加来源',
            test_source: '测试',
            edit_source: '编辑',
            delete_source: '删除',
            save: '保存',
            cancel: '取消',
            active: '活跃',
            inactive: '未活跃',
            never: '从未',
            last: '上次',
            articles_label: '文章',
            no_articles: '暂无文章',
            load_more: '加载更多',
            published: '发布时间',
            collected: '采集时间',
            sentiment: '情感',
            category: '分类',
            read_more: '阅读更多',
            fill_required: '请填写必要字段',
            add_success: '新闻源添加成功！',
            add_failed: '添加失败:',
            update_success: '新闻源更新成功！',
            update_failed: '更新失败:',
            delete_success: '新闻源删除成功！',
            delete_failed: '删除失败:',
            test_success: '测试成功:',
            error_generic: '发生错误:',
        },
    };

    let currentLang = localStorage.getItem(STORAGE_KEY) || 'en';

    function t(key) {
        const pack = translations[currentLang] || translations.en;
        return pack[key] || translations.en[key] || key;
    }

    function setLanguage(lang) {
        if (!translations[lang]) return;
        currentLang = lang;
        localStorage.setItem(STORAGE_KEY, lang);
        document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
        applyTranslations();
    }

    function toggleLanguage() {
        setLanguage(currentLang === 'en' ? 'zh' : 'en');
    }

    function applyTranslations() {
        document.querySelectorAll('[data-i18n]').forEach((el) => {
            const key = el.getAttribute('data-i18n');
            const text = t(key);
            if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
                el.placeholder = text;
            } else {
                el.textContent = text;
            }
        });

        document.querySelectorAll('[data-i18n-title]').forEach((el) => {
            el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
        });

        const switcher = document.getElementById('langSwitcher');
        if (switcher) {
            switcher.textContent = t('lang_switch');
        }
    }

    function initI18n() {
        document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
        applyTranslations();
        const switcher = document.getElementById('langSwitcher');
        if (switcher) {
            switcher.addEventListener('click', (e) => {
                e.preventDefault();
                toggleLanguage();
            });
        }
    }

    global.NewsAgentI18n = {
        t,
        setLanguage,
        toggleLanguage,
        getLanguage: () => currentLang,
        init: initI18n,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initI18n);
    } else {
        initI18n();
    }
})(window);
