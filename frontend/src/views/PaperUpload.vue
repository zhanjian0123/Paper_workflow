<template>
  <Layout>
    <ContentContainer size="xl">
      <PageContent spacing="loose" class="paper-upload">
        <PageHeader
          title="论文上传"
          subtitle="上传本地 PDF 并快速发起后续分析工作流"
        />

        <el-card class="upload-card feature-panel feature-panel--blue">
          <template #header>
            <div class="card-header">
              <span>上传 PDF 论文</span>
            </div>
          </template>
          
          <!-- 拖拽上传区域 -->
          <el-upload
            ref="uploadRef"
            drag
            multiple
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".pdf"
            class="upload-area"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF 格式，可一次上传多个文件
              </div>
            </template>
          </el-upload>
          
          <!-- 文件列表 -->
          <div v-if="fileList.length > 0" class="file-list">
            <h4>已选择文件 ({{ fileList.length }})</h4>
            <div v-for="(file, index) in fileList" :key="index" class="file-item">
              <el-icon><document /></el-icon>
              <span class="file-name">{{ file.name }}</span>
              <el-tag size="small" :type="file.status === 'uploaded' ? 'success' : 'info'">
                {{ file.status === 'uploaded' ? '已上传' : '待上传' }}
              </el-tag>
            </div>
          </div>
          
          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button 
              type="primary" 
              :loading="uploading" 
              @click="handleUpload"
              :disabled="fileList.length === 0"
            >
              {{ uploading ? '上传中...' : '开始上传' }}
            </el-button>
            <el-button @click="handleClear">清空列表</el-button>
            <el-button 
              type="success" 
              @click="handleCreateWorkflow"
              :disabled="uploadedPapers.length === 0"
            >
              从选中论文创建工作流
            </el-button>
          </div>
        </el-card>

        <!-- 已上传的论文列表 -->
        <el-card class="papers-card feature-panel feature-panel--blue" v-if="uploadedPapers.length > 0">
          <template #header>
            <div class="card-header">
              <span>已上传的论文</span>
              <el-button size="small" @click="loadPapers">
                <el-icon><refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>
          
          <div class="table-shell table-shell--wide">
            <el-table :data="uploadedPapers" style="width: 100%">
            <el-table-column type="selection" width="55" @selection-change="handleSelectionChange" />
            <el-table-column prop="title" label="标题" min-width="200" />
            <el-table-column prop="source" label="来源" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.source === 'local_upload'" type="info">本地上传</el-tag>
                <el-tag v-else>{{ row.source }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" @click="handleParse(row)">解析</el-button>
                <el-button size="small" @click="handlePreview(row)">预览</el-button>
              </template>
            </el-table-column>
            </el-table>
          </div>
        </el-card>
      </PageContent>
    </ContentContainer>

    <!-- 解析结果对话框 -->
    <el-dialog v-model="parseDialogVisible" title="论文解析结果" width="60%">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="标题">{{ parseResult.title }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ parseResult.abstract || '暂无' }}</el-descriptions-item>
        <el-descriptions-item label="页数">{{ parseResult.pages || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadApi } from '@/api'
import { Layout, ContentContainer, PageContent, PageHeader } from '@/components/layout'

const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)
const uploadedPapers = ref([])
const selectedPapers = ref([])
const parseDialogVisible = ref(false)
const parseResult = ref({})

// 加载已上传的论文
const loadPapers = async () => {
  try {
    const res = await uploadApi.getPapers({ source: 'local_upload' })
    uploadedPapers.value = res.data.items || []
  } catch (error) {
    console.error('加载论文失败:', error)
  }
}

// 处理文件变化
const handleFileChange = (file) => {
  if (!fileList.value.find(f => f.name === file.name)) {
    fileList.value.push({
      name: file.name,
      raw: file.raw,
      status: 'pending',
    })
  }
}

// 处理文件移除
const handleFileRemove = (file) => {
  fileList.value = fileList.value.filter(f => f.name !== file.name)
}

// 清空列表
const handleClear = () => {
  fileList.value = []
  uploadRef.value?.clearFiles()
}

// 上传文件
const handleUpload = async () => {
  const pendingFiles = fileList.value.filter(f => f.status === 'pending')
  if (pendingFiles.length === 0) {
    ElMessage.info('没有待上传的文件')
    return
  }
  
  uploading.value = true
  const filesToUpload = pendingFiles.map(f => f.raw)
  
  try {
    const res = await uploadApi.uploadPapersBatch(filesToUpload)
    const { results, uploaded } = res.data
    
    // 更新文件状态
    fileList.value.forEach(file => {
      const uploadedFile = results.find(r => r.title === file.name.replace('.pdf', ''))
      if (uploadedFile) {
        file.status = 'uploaded'
        file.paperId = uploadedFile.paper_id
      }
    })
    
    ElMessage.success(`成功上传 ${uploaded} 篇论文`)
    loadPapers()
  } catch (error) {
    ElMessage.error('上传失败：' + (error.response?.data?.detail || error.message))
  } finally {
    uploading.value = false
  }
}

// 解析论文
const handleParse = async (row) => {
  try {
    const res = await uploadApi.parsePaper(row.paper_id)
    parseResult.value = res.data
    parseDialogVisible.value = true
    ElMessage.success('解析成功')
  } catch (error) {
    ElMessage.error('解析失败：' + (error.response?.data?.detail || error.message))
  }
}

// 预览论文
const handlePreview = (row) => {
  window.open(`/api/papers/${row.paper_id}/pdf`, '_blank')
}

// 处理选择变化
const handleSelectionChange = (selection) => {
  selectedPapers.value = selection.map(p => p.paper_id)
}

// 创建工作流
const handleCreateWorkflow = () => {
  if (selectedPapers.value.length === 0) {
    ElMessage.warning('请先选择论文')
    return
  }
  uploadApi.createWorkflowFromPapers(selectedPapers.value, '本地论文分析')
    .then(res => {
      ElMessage.success('工作流创建成功')
      window.location.href = `/workflows/${res.data.id}`
    })
    .catch(error => {
      ElMessage.error('创建失败：' + (error.response?.data?.detail || error.message))
    })
}

onMounted(() => {
  loadPapers()
})
</script>

<style scoped>
.paper-upload {
  animation: fadeInUp 0.5s var(--ease-out);
}

.upload-card, .papers-card {
  background: var(--bg-primary);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-area {
  width: 100%;
}

.file-list {
  margin-top: 20px;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 4px;
}

.file-list h4 {
  margin-bottom: 10px;
  color: #666;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  gap: 10px;
}

.file-name {
  flex: 1;
  color: #333;
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>
