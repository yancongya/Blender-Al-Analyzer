<script setup lang='ts'>
interface Emit {
  (e: 'click'): void
}

interface Props {
  size?: 'small' | 'medium' | 'large'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium',
})

const emit = defineEmits<Emit>()

function handleClick() {
  emit('click')
}
</script>

<template>
  <button
    :class="[
      'flex items-center justify-center transition rounded-full hover:bg-neutral-100 dark:hover:bg-[#414755]',
      props.size === 'small' ? 'w-8 h-8' : props.size === 'large' ? 'w-12 h-12' : 'w-10 h-10'
    ]"
    @click="handleClick"
  >
    <slot />
  </button>
</template>
