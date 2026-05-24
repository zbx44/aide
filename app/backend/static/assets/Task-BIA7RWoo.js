import{h,x as C,e as x,s as v}from"./index-B4nPP_i4.js";import{_ as V,d as D,f as l,w as t,h as r,o as $,e as n,t as k,c as s}from"./index-CBRtnNuw.js";import"./index-DcNlVx-A.js";const L=`name: "新任务"
description: "任务描述"
enabled: true

schedule:
  cron: "0 8 * * *"

database:
  host: "192.168.1.10"
  standby: "192.168.1.11"
  port: 5236
  username: "dmdb"
  password: ""
  database: "lczx"

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
`,Y={name:"Task",data(){return{tasks:[],showCreateDialog:!1,newTaskYaml:L}},async mounted(){await this.loadTasks()},methods:{async loadTasks(){try{const{data:o}=await v();this.tasks=o}catch(o){console.error(o)}},async createTask(){try{await x(this.newTaskYaml),this.$message.success("任务创建成功"),this.showCreateDialog=!1,await this.loadTasks()}catch(o){this.$message.error(`创建失败: ${o.message}`)}},async runTask(o){try{const{data:e}=await C(o);this.$message.success(`执行完成: ${e.status}`)}catch(e){this.$message.error(`执行失败: ${e.message}`)}},async deleteTask(o){try{await h(o),this.$message.success("已删除"),await this.loadTasks()}catch(e){this.$message.error(`删除失败: ${e.message}`)}}}},z={class:"task-page",style:{padding:"20px"}},A={style:{display:"flex","justify-content":"space-between"}};function M(o,e,E,B,i,m){const d=r("el-button"),u=r("el-table-column"),y=r("el-tag"),b=r("el-table"),c=r("el-card"),_=r("el-col"),g=r("el-row"),w=r("el-input"),T=r("el-dialog");return $(),D("div",z,[l(g,{gutter:20},{default:t(()=>[l(_,{span:16},{default:t(()=>[l(c,null,{header:t(()=>[s("div",A,[e[5]||(e[5]=s("span",null,"📊 定时分析任务",-1)),l(d,{type:"primary",size:"small",onClick:e[0]||(e[0]=a=>i.showCreateDialog=!0)},{default:t(()=>[...e[4]||(e[4]=[n(" 新建任务 ",-1)])]),_:1})])]),default:t(()=>[l(b,{data:i.tasks,stripe:""},{default:t(()=>[l(u,{prop:"name",label:"任务名称"}),l(u,{prop:"description",label:"描述"}),l(u,{prop:"schedule",label:"调度"},{default:t(({row:a})=>{var p,f;return[n(k(((p=a.schedule)==null?void 0:p.cron)||((f=a.schedule)==null?void 0:f.interval)+"s"||"-"),1)]}),_:1}),l(u,{prop:"enabled",label:"状态",width:"80"},{default:t(({row:a})=>[l(y,{type:a.enabled?"success":"info"},{default:t(()=>[n(k(a.enabled?"启用":"停用"),1)]),_:2},1032,["type"])]),_:1}),l(u,{label:"操作",width:"150"},{default:t(({row:a})=>[l(d,{size:"small",type:"primary",link:"",onClick:p=>m.runTask(a.name)},{default:t(()=>[...e[6]||(e[6]=[n(" 执行 ",-1)])]),_:1},8,["onClick"]),l(d,{size:"small",type:"danger",link:"",onClick:p=>m.deleteTask(a.name)},{default:t(()=>[...e[7]||(e[7]=[n(" 删除 ",-1)])]),_:1},8,["onClick"])]),_:1})]),_:1},8,["data"])]),_:1})]),_:1}),l(_,{span:8},{default:t(()=>[l(c,null,{header:t(()=>[...e[8]||(e[8]=[s("span",null,"📝 任务说明",-1)])]),default:t(()=>[e[9]||(e[9]=s("div",{style:{"font-size":"13px","line-height":"1.8",color:"#666"}},[s("p",null,"每个分析任务包含："),s("ul",null,[s("li",null,[s("b",null,"调度配置"),n("：cron表达式或间隔时间")]),s("li",null,[s("b",null,"SQL查询"),n("：从达梦数据库取数")]),s("li",null,[s("b",null,"分析提示词"),n("：告诉AI如何分析")]),s("li",null,[s("b",null,"输出模板"),n("：报告格式和文件名")]),s("li",null,[s("b",null,"通知配置"),n("：完成后推送（可选）")])]),s("p",null,"配置使用YAML格式，支持变量替换。")],-1))]),_:1})]),_:1})]),_:1}),l(T,{modelValue:i.showCreateDialog,"onUpdate:modelValue":e[3]||(e[3]=a=>i.showCreateDialog=a),title:"新建分析任务",width:"700px"},{footer:t(()=>[l(d,{onClick:e[2]||(e[2]=a=>i.showCreateDialog=!1)},{default:t(()=>[...e[10]||(e[10]=[n("取消",-1)])]),_:1}),l(d,{type:"primary",onClick:m.createTask},{default:t(()=>[...e[11]||(e[11]=[n("创建",-1)])]),_:1},8,["onClick"])]),default:t(()=>[l(w,{modelValue:i.newTaskYaml,"onUpdate:modelValue":e[1]||(e[1]=a=>i.newTaskYaml=a),type:"textarea",rows:18,placeholder:"粘贴任务YAML配置..."},null,8,["modelValue"])]),_:1},8,["modelValue"])])}const U=V(Y,[["render",M]]);export{U as default};
