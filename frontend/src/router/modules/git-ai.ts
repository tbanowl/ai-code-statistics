import { system } from "@/router/enums";

const Layout = () => import("@/layout/index.vue");

export default {
  path: "/git-ai",
  name: "GitAiManage",
  component: Layout,
  redirect: "/git-ai/releases",
  meta: {
    icon: "ri:git-branch-line",
    title: "Git-AI 管理",
    rank: system + 10
  },
  children: [
    {
      path: "/git-ai/releases",
      name: "GitAiReleaseManage",
      component: () => import("@/views/git-ai-release/index.vue"),
      meta: { title: "发布管理" }
    }
  ]
} satisfies RouteConfigsTable;
