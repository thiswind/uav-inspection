export interface AgentMessage {
	role: 'agent' | 'user'
	content: string
	type?: 'info' | 'warning' | 'action'
	time?: string
}

export interface AgentCommand {
	content: string
	metadata?: Record<string, any>
}
