import { buildPestUrl, pestHttp, type ApiResponse } from './request'

export interface ReportItem {
	id: string
	title: string
	generated_at: string
	format: 'pdf' | 'csv'
	attachment_count?: number
	size_bytes?: number
}

// 获取报告列表
export const listReports = (): Promise<ApiResponse<ReportItem[]>> =>
	pestHttp.get<ReportItem[]>('/reports')

// 构建报告下载链接
export const buildReportDownloadUrl = (reportId: string): string =>
	buildPestUrl(`/reports/${reportId}/download`)
