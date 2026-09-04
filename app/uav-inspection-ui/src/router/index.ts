import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const PestInspectionView = () => import('../views/PestInspectionView.vue')
const RoseYieldView = () => import('../views/RoseYieldView.vue')
const HeatmapFlowView = () => import('../views/HeatmapFlowView.vue')
const TelecomInspectionView = () => import('../views/TelecomInspectionView.vue')
const AssetsUploadView = () => import('../views/AssetsUploadView.vue')
const RoofInspectionView = () => import('../views/RoofInspectionView.vue')
const PowerLineInspectionView = () => import('../views/PowerLineInspectionView.vue')
const WallInspectionView = () => import('../views/WallInspectionView.vue')
const PruningInspectionView = () => import('../views/PruningInspectionView.vue')
const DigitalRoseGardenView = () => import('../views/DigitalRoseGardenView.vue')
const VegetationMeasurementView = () => import('../views/VegetationMeasurementView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/telecom', name: 'telecom', component: TelecomInspectionView },
    { path: '/assets', name: 'assets', component: AssetsUploadView },
    { path: '/pest', name: 'pest-inspection', component: PestInspectionView },
    { path: '/heatmap-flow', name: 'heatmap-flow', component: HeatmapFlowView },
    { path: '/power', name: 'power', component: PowerLineInspectionView },
    { path: '/roof', name: 'roof', component: RoofInspectionView },
    { path: '/wall', name: 'wall', component: WallInspectionView },
    { path: '/pruning', name: 'pruning', component: PruningInspectionView },
    { path: '/height', name: 'height', component: VegetationMeasurementView, props: { mode: 'height' } },
    { path: '/area', name: 'area', component: VegetationMeasurementView, props: { mode: 'area' } },
    { path: '/rose-digital', name: 'rose-digital', component: DigitalRoseGardenView },
    { path: '/rose-yield', name: 'rose-yield', component: RoseYieldView },
  ],
})

export default router
