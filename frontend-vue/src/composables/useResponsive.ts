import { ref, computed, onMounted, onUnmounted } from 'vue'

export interface Breakpoints {
  xs: number
  sm: number
  md: number
  lg: number
  xl: number
  '2xl': number
}

const defaultBreakpoints: Breakpoints = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536
}

export function useResponsive(customBreakpoints?: Partial<Breakpoints>) {
  const breakpoints = { ...defaultBreakpoints, ...customBreakpoints }

  const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 0)
  const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 0)

  const current = computed<keyof Breakpoints>(() => {
    if (windowWidth.value >= breakpoints['2xl']) return '2xl'
    if (windowWidth.value >= breakpoints.xl) return 'xl'
    if (windowWidth.value >= breakpoints.lg) return 'lg'
    if (windowWidth.value >= breakpoints.md) return 'md'
    if (windowWidth.value >= breakpoints.sm) return 'sm'
    return 'xs'
  })

  const isMobile = computed(() => windowWidth.value < breakpoints.md)
  const isTablet = computed(() =>
    windowWidth.value >= breakpoints.md && windowWidth.value < breakpoints.lg
  )
  const isDesktop = computed(() => windowWidth.value >= breakpoints.lg)

  const isXs = computed(() => current.value === 'xs')
  const isSm = computed(() => current.value === 'sm')
  const isMd = computed(() => current.value === 'md')
  const isLg = computed(() => current.value === 'lg')
  const isXl = computed(() => current.value === 'xl')
  const is2xl = computed(() => current.value === '2xl')

  function isGreaterThan(breakpoint: keyof Breakpoints): boolean {
    return windowWidth.value > breakpoints[breakpoint]
  }

  function isLessThan(breakpoint: keyof Breakpoints): boolean {
    return windowWidth.value < breakpoints[breakpoint]
  }

  function isBetween(min: keyof Breakpoints, max: keyof Breakpoints): boolean {
    return windowWidth.value >= breakpoints[min] && windowWidth.value < breakpoints[max]
  }

  let resizeHandler: (() => void) | null = null

  onMounted(() => {
    resizeHandler = () => {
      windowWidth.value = window.innerWidth
      windowHeight.value = window.innerHeight
    }
    window.addEventListener('resize', resizeHandler)
  })

  onUnmounted(() => {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
    }
  })

  return {
    windowWidth,
    windowHeight,
    current,
    isMobile,
    isTablet,
    isDesktop,
    isXs,
    isSm,
    isMd,
    isLg,
    isXl,
    is2xl,
    isGreaterThan,
    isLessThan,
    isBetween,
    breakpoints
  }
}
