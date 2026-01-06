<script setup lang='ts'>
import pkg from '../../../../package.json'
</script>

<template>
  <div class="p-4 space-y-4">
    <h2 class="text-xl font-bold">
      {{ $t('setting.aiNodeAnalyzer') }} - {{ pkg.version }}
    </h2>
    <div class="space-y-4">
      <p>{{ $t('setting.aiNodeAnalyzerDesc') }}</p>

      <div>
        <h3 class="font-semibold mb-2">{{ $t('setting.aiNodeAnalyzerFeatures') }}</h3>
        <ul class="list-disc pl-6 space-y-1">
          <li>{{ $t('setting.featureParseNodes') }}</li>
          <li>{{ $t('setting.featurePanel') }}</li>
          <li>{{ $t('setting.featureNodeType') }}</li>
          <li>{{ $t('setting.featureAIProvider') }}</li>
          <li>{{ $t('setting.featureSaveResult') }}</li>
          <li>{{ $t('setting.featureBackendServer') }}</li>
        </ul>
      </div>

      <div>
        <h3 class="font-semibold mb-2">{{ $t('setting.projectInfo') }}</h3>
        <p>{{ $t('setting.repository') }}：
          <a
            class="text-blue-600 dark:text-blue-500"
            href="https://github.com/yancongya/Blender-Al-Analyzer"
            target="_blank"
          >
            https://github.com/yancongya/Blender-Al-Analyzer
          </a>
        </p>
        <p>{{ $t('setting.author') }}：yancongya</p>
        <p>{{ $t('setting.license') }}：MIT</p>
      </div>

      <!-- 原始项目信息保留 -->
      <div class="pt-4 border-t border-neutral-300 dark:border-neutral-600">
        <h3 class="font-semibold mb-2">{{ $t('setting.originalProject') }}</h3>
        <p>
          {{ $t("setting.originalProject") }}
          <a
            class="text-blue-600 dark:text-blue-500"
            href="https://github.com/Chanzhaoyu/chatgpt-web"
            target="_blank"
          >
            {{ $t("setting.originalProjectLink") }}
          </a>
          {{ $t("setting.originalLicense") }}
        </p>
        <p>
          {{ $t("setting.originalCredit") }}
        </p>
      </div>
    </div>
  </div>
</template>
