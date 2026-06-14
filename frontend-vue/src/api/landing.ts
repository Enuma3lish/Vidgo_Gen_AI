/**
 * Landing Page API Client
 * Fetches content for landing page sections
 */
import apiClient from './client'

// Types
export interface StatItem {
  value: string
  label: string
  color: string
}

export interface LandingStats {
  users: StatItem
  time_saved: StatItem
  conversion: StatItem
}

export interface FeatureItem {
  id: string
  icon: string
  gradient: string
  title: string
  title_zh: string
  description: string
  description_zh: string
}

export interface ExampleItem {
  id: string
  category: string
  category_label: string
  duration: string
  title: string
  title_zh: string
  description: string
  description_zh: string
  thumbnail: string
  video_url?: string
}

export interface TestimonialItem {
  id: string
  name: string
  title: string
  company: string
  company_type: string
  avatar?: string
  rating: number
  quote: string
  quote_zh: string
}

export interface PricingPlan {
  id: string
  name: string
  name_zh: string
  price: number
  original_price: number
  currency: string
  period: string
  description: string
  description_zh: string
  features: string[]
  features_zh: string[]
  is_featured: boolean
  badge?: string
}

export interface FAQItem {
  id: string
  question: string
  question_zh: string
  answer: string
  answer_zh: string
}

export interface ContactForm {
  name: string
  email: string
  company?: string
  message: string
}

// API Functions
export async function getLandingStats(): Promise<LandingStats> {
  const { data } = await apiClient.get<LandingStats>('/api/v1/landing/stats')
  return data
}

export async function getFeatures(): Promise<FeatureItem[]> {
  const { data } = await apiClient.get<FeatureItem[]>('/api/v1/landing/features')
  return data
}

export async function getExamples(category?: string): Promise<ExampleItem[]> {
  const params = category && category !== 'all' ? { category } : {}
  const { data } = await apiClient.get<ExampleItem[]>('/api/v1/landing/examples', { params })
  return data
}

export async function getTestimonials(): Promise<TestimonialItem[]> {
  const { data } = await apiClient.get<TestimonialItem[]>('/api/v1/landing/testimonials')
  return data
}

export async function getPricing(): Promise<PricingPlan[]> {
  const { data } = await apiClient.get<PricingPlan[]>('/api/v1/landing/pricing')
  return data
}

export async function getFAQ(): Promise<FAQItem[]> {
  const { data } = await apiClient.get<FAQItem[]>('/api/v1/landing/faq')
  return data
}

export async function submitContactForm(form: ContactForm): Promise<{ success: boolean; message: string }> {
  const { data } = await apiClient.post('/api/v1/landing/contact', form)
  return data
}

export async function demoGenerate(): Promise<{ success: boolean; task_id: string }> {
  const { data } = await apiClient.post('/api/v1/landing/demo-generate')
  return data
}

// Export all
export default {
  getLandingStats,
  getFeatures,
  getExamples,
  getTestimonials,
  getPricing,
  getFAQ,
  submitContactForm,
  demoGenerate
}
