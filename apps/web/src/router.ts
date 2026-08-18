import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";
import SectionView from "./views/SectionView.vue";
import CoreAgentView from "./views/CoreAgentView.vue";
import LogsView from "./views/LogsView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HomeView },
    {
      path: "/core-agent",
      component: CoreAgentView,
    },
    {
      path: "/github-stars",
      component: SectionView,
      props: { section: "github-stars", title: "Github新星", description: "按日期筛选 GitHub 上升项目。第一阶段可为空或少量数据。" },
    },
    {
      path: "/model-platform",
      component: SectionView,
      props: { section: "model-platform", title: "大模型", description: "按日期筛选大模型产品与平台内容。" },
    },
    {
      path: "/agent-products",
      component: SectionView,
      props: { section: "agent-products", title: "Agent", description: "按日期筛选 Agent 产品与应用内容。" },
    },
    {
      path: "/finance-ai",
      component: SectionView,
      props: { section: "finance-ai", title: "金融AI", description: "按日期筛选金融 AI 内容。第一阶段可为空或少量数据。" },
    },
    {
      path: "/others",
      component: SectionView,
      props: { section: "others", title: "其他", description: "无法归入以上分类的内容。" },
    },
    { path: "/system-logs", component: LogsView },
  ],
});
