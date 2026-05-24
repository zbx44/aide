import{i as x,z as v,e as D,u as V}from"./index-B47HzWK3.js";import{_ as $,o as A,d as L,f as t,w as l,h as o,e as n,t as k,c as a}from"./index-DMBPza9q.js";import"./index-DcNlVx-A.js";const Y=`name: "新任务"
description: "任务描述"
enabled: true

schedule:
  cron: "0 8 * * *"

database:
  host: "127.0.0.1"
  standby: "127.0.0.2"
  port: 5236
  username: "username"
  password: ""
  database: "database"

sql: |
  SELECT * FROM your_table LIMIT 10

prompt: |
  请分析以下数据：
  {{data}}

output:
  format: "docx"
  filename: "分析报告_{{date}}.docx"
  save_path: "output/reports/"

notify:
  enabled: false
`,z={name:"Task",data(){return{tasks:[],showCreateDialog:!1,newTaskYaml:Y}},async mounted(){await this.loadTasks()},methods:{async loadTasks(){try{const{data:r}=await V();this.tasks=r}catch(r){console.error(r)}},async createTask(){try{await D(this.newTaskYaml),this.$message.success("任务创建成功"),this.showCreateDialog=!1,await this.loadTasks()}catch(r){this.$message.error(`创建失败: ${r.message}`)}},async runTask(r){try{const{data:e}=await v(r);this.$message.success(`执行完成: ${e.status}`)}catch(e){this.$message.error(`执行失败: ${e.message}`)}},async deleteTask(r){try{await x(r),this.$message.success("已删除"),await this.loadTasks()}catch(e){this.$message.error(`删除失败: ${e.message}`)}}}},M={class:"task-page",style:{padding:"20px"}},E={style:{display:"flex","justify-content":"space-between"}};function B(r,e,I,N,i,m){const y=o("DataAnalysis"),b=o("el-icon"),d=o("el-button"),u=o("el-table-column"),g=o("el-tag"),w=o("el-table"),c=o("el-card"),_=o("el-col"),T=o("el-row"),h=o("el-input"),C=o("el-dialog");return A(),L("div",M,[t(T,{gutter:20},{default:l(()=>[t(_,{span:16},{default:l(()=>[t(c,null,{header:l(()=>[a("div",E,[a("span",null,[t(b,null,{default:l(()=>[t(y)]),_:1}),e[4]||(e[4]=n(" 定时分析任务",-1))]),t(d,{type:"primary",size:"small",onClick:e[0]||(e[0]=s=>i.showCreateDialog=!0)},{default:l(()=>[...e[5]||(e[5]=[n(" 新建任务 ",-1)])]),_:1})])]),default:l(()=>[t(w,{data:i.tasks,stripe:""},{default:l(()=>[t(u,{prop:"name",label:"任务名称"}),t(u,{prop:"description",label:"描述"}),t(u,{prop:"schedule",label:"调度"},{default:l(({row:s})=>{var p,f;return[n(k(((p=s.schedule)==null?void 0:p.cron)||((f=s.schedule)==null?void 0:f.interval)+"s"||"-"),1)]}),_:1}),t(u,{prop:"enabled",label:"状态",width:"80"},{default:l(({row:s})=>[t(g,{type:s.enabled?"success":"info"},{default:l(()=>[n(k(s.enabled?"启用":"停用"),1)]),_:2},1032,["type"])]),_:1}),t(u,{label:"操作",width:"150"},{default:l(({row:s})=>[t(d,{size:"small",type:"primary",link:"",onClick:p=>m.runTask(s.name)},{default:l(()=>[...e[6]||(e[6]=[n(" 执行 ",-1)])]),_:1},8,["onClick"]),t(d,{size:"small",type:"danger",link:"",onClick:p=>m.deleteTask(s.name)},{default:l(()=>[...e[7]||(e[7]=[n(" 删除 ",-1)])]),_:1},8,["onClick"])]),_:1})]),_:1},8,["data"])]),_:1})]),_:1}),t(_,{span:8},{default:l(()=>[t(c,null,{header:l(()=>[...e[8]||(e[8]=[a("span",null,"📝 任务说明",-1)])]),default:l(()=>[e[9]||(e[9]=a("div",{style:{"font-size":"13px","line-height":"1.8",color:"#666"}},[a("p",null,"每个分析任务包含："),a("ul",null,[a("li",null,[a("b",null,"调度配置"),n("：cron表达式或间隔时间")]),a("li",null,[a("b",null,"SQL查询"),n("：从达梦数据库取数")]),a("li",null,[a("b",null,"分析提示词"),n("：告诉AI如何分析")]),a("li",null,[a("b",null,"输出模板"),n("：报告格式和文件名")]),a("li",null,[a("b",null,"通知配置"),n("：完成后推送（可选）")])]),a("p",null,"配置使用YAML格式，支持变量替换。")],-1))]),_:1})]),_:1})]),_:1}),t(C,{modelValue:i.showCreateDialog,"onUpdate:modelValue":e[3]||(e[3]=s=>i.showCreateDialog=s),title:"新建分析任务",width:"700px"},{footer:l(()=>[t(d,{onClick:e[2]||(e[2]=s=>i.showCreateDialog=!1)},{default:l(()=>[...e[10]||(e[10]=[n("取消",-1)])]),_:1}),t(d,{type:"primary",onClick:m.createTask},{default:l(()=>[...e[11]||(e[11]=[n("创建",-1)])]),_:1},8,["onClick"])]),default:l(()=>[t(h,{modelValue:i.newTaskYaml,"onUpdate:modelValue":e[1]||(e[1]=s=>i.newTaskYaml=s),type:"textarea",rows:18,placeholder:"粘贴任务YAML配置..."},null,8,["modelValue"])]),_:1},8,["modelValue"])])}const j=$(z,[["render",B]]);export{j as default};
