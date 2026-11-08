export interface Monitor {id:number;name:string;url:string;method:string;expected_status:number;interval_seconds:number;failure_threshold:number;consecutive_failures:number;is_active:boolean;next_check_at:string}
export interface Check {id:number;monitor_id:number;checked_at:string;latency_ms:number|null;status_code:number|null;success:boolean;error:string|null}
export interface Metrics {monitor_id:number;window_hours:number;sample_count:number;availability_pct:number|null;avg_latency_ms:number|null;p50_latency_ms:number|null;p95_latency_ms:number|null;p99_latency_ms:number|null;checks:Check[]}
export interface Incident {id:number;monitor_id:number;opened_at:string;resolved_at:string|null;reason:string}
export interface AlertRule {id:number;monitor_id:number;name:string;channel:'email'|'webhook';destination:string;notify_on_open:boolean;notify_on_recovery:boolean;is_active:boolean;created_at:string}
export interface AlertEvent {id:number;alert_rule_id:number;incident_id:number;event_type:string;status:string;attempts:number;delivered_at:string|null;last_error:string|null}
export interface Summary {monitored_apis:number;active_monitors:number;open_incidents:number}
export class ApiError extends Error { constructor(public status:number,message:string){super(message)} }
let apiKey = sessionStorage.getItem('pulsewatch-token')||'';
export function getKey(){return apiKey}
export function setKey(value:string){apiKey=value.trim();if(apiKey)sessionStorage.setItem('pulsewatch-token',apiKey);else sessionStorage.removeItem('pulsewatch-token')}
async function request<T>(path:string, options:RequestInit={}):Promise<T> {
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(apiKey?{'Authorization':`Bearer ${apiKey}`}:{}),...options.headers}});
  if(response.status===204)return undefined as T;
  if(!response.ok){let message=`Request failed (${response.status})`;try{const body=await response.json();message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail??body)}catch{}throw new ApiError(response.status,message)}
  return response.json() as Promise<T>
}
export const api={
  login:async(email:string,password:string)=>{
    const response=await fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
    if(!response.ok)throw new ApiError(response.status,(await response.json()).detail??'Login failed');
    const data=await response.json() as {access_token:string};setKey(data.access_token);return data;
  },
  me:()=>request<{email:string;role:string}>('/api/v1/auth/me'),
  logout:async()=>{try{await request<void>('/api/v1/auth/logout',{method:'POST'})}finally{setKey('')}},
  health:()=>fetch('/health').then(r=>{if(!r.ok)throw new Error('Backend unavailable');return r.json()}),
  summary:()=>request<Summary>('/api/v1/dashboard/summary'),
  monitors:()=>request<Monitor[]>('/api/v1/monitors'),
  metrics:(id:number,hours:number)=>request<Metrics>(`/api/v1/monitors/${id}/metrics?hours=${hours}`),
  incidents:()=>request<Incident[]>('/api/v1/incidents'),
  rules:()=>request<AlertRule[]>('/api/v1/alert-rules'),
  events:()=>request<AlertEvent[]>('/api/v1/alert-events'),
  addMonitor:(payload:object)=>request<Monitor>('/api/v1/monitors',{method:'POST',body:JSON.stringify(payload)}),
  updateMonitor:(id:number,payload:object)=>request<Monitor>(`/api/v1/monitors/${id}`,{method:'PATCH',body:JSON.stringify(payload)}),
  deleteMonitor:(id:number)=>request<void>(`/api/v1/monitors/${id}`,{method:'DELETE'}),
  runCheck:(id:number)=>request<Check>(`/api/v1/monitors/${id}/check`,{method:'POST'}),
  addRule:(payload:object)=>request<AlertRule>('/api/v1/alert-rules',{method:'POST',body:JSON.stringify(payload)}),
  disableRule:(id:number)=>request<void>(`/api/v1/alert-rules/${id}`,{method:'DELETE'}),
  report:(id:number)=>request<Record<string,unknown>>(`/api/v1/incidents/${id}/report`)
};
