<template>
  <div class="train-tab">
    <h2>模型训练</h2>

    <!-- 训练配置面板 -->
    <div class="train-config">
      <el-input v-model="trainName" placeholder="训练名称" />
      <el-select v-model="trainModel" placeholder="选择训练模型">
        <el-option
          v-for="m in models"
          :key="m.model_id"
          :label="m.model_id"
          :value="m.model_id"
        />
      </el-select>
      <el-button type="success" @click="startTraining">开始训练</el-button>
    </div>

    <!-- 训练任务列表 -->
    <div class="train-tasks" v-if="trainTasks.length">
      <h3>训练任务列表</h3>
      <div v-for="(task, index) in trainTasks" :key="index" class="task-item">
        {{ task.name }}（{{ task.model }}）
        <el-button size="mini" type="danger" @click="removeTrainTask(index)">删除</el-button>
      </div>
    </div>

    <!-- 训练结果展示 -->
    <div class="train-result" v-if="trainResults.length">
      <h3>训练结果</h3>
      <el-table :data="trainResults" stripe>
        <el-table-column prop="name" label="任务名称" />
        <el-table-column prop="model" label="模型" />
        <el-table-column prop="accuracy" label="准确率" />
        <el-table-column prop="loss" label="损失" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

// 训练配置
const trainName = ref('')
const trainModel = ref('')
const trainTasks = ref([])
const trainResults = ref([])

// 模型列表（可通过接口获取）
const models = ref([
  { model_id: '模型A' },
  { model_id: '模型B' },
  { model_id: '模型C' }
])

// 开始训练
function startTraining() {
  if (!trainName.value || !trainModel.value) return
  trainTasks.value.push({ name: trainName.value, model: trainModel.value })

  // 模拟训练结果
  trainResults.value.push({
    name: trainName.value,
    model: trainModel.value,
    accuracy: (Math.random() * 0.3 + 0.7).toFixed(2),
    loss: (Math.random() * 0.2 + 0.1).toFixed(2)
  })

  // 清空输入
  trainName.value = ''
  trainModel.value = ''
}

// 删除训练任务
function removeTrainTask(index) {
  trainTasks.value.splice(index, 1)
  trainResults.value.splice(index, 1)
}
</script>

<style scoped>
.train-tab {
  padding: 10px;
}

.train-config {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 15px;
}

.train-tasks {
  margin-bottom: 15px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 5px 0;
}

.train-result {
  margin-top: 20px;
}
</style>
