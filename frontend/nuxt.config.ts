import tailwindcss from "@tailwindcss/vite"

export default defineNuxtConfig({
	css: ["~/assets/css/tailwind.css"],
	app: {
		head: {
			script: [
				{
					src: "https://telegram.org/js/telegram-web-app.js",
					defer: false,
				},
			],
		},
	},
	vite: {
		plugins: [tailwindcss()],
	},

	compatibilityDate: "2025-07-15",
	devtools: { enabled: false },
	modules: ["shadcn-nuxt"],
	runtimeConfig: {
		public: {
			apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000",
			counterPath: process.env.NUXT_PUBLIC_COUNTER_PATH || "/counter",
			uploadImagePath: process.env.NUXT_PUBLIC_UPLOAD_IMAGE_PATH || "/api/uploads/image",
			uploadListPath: process.env.NUXT_PUBLIC_UPLOAD_LIST_PATH || "/api/uploads/list",
			uploadRenamePath: process.env.NUXT_PUBLIC_UPLOAD_RENAME_PATH || "/api/uploads/rename",
			uploadDeleteBasePath: process.env.NUXT_PUBLIC_UPLOAD_DELETE_BASE_PATH || "/api/uploads/file/",
			uploadPreviewBasePath: process.env.NUXT_PUBLIC_UPLOAD_PREVIEW_BASE_PATH || "/api/uploads/image/",
			genaiTextPath: process.env.NUXT_PUBLIC_GENAI_TEXT_PATH || "/api/genai/text",
			genaiImagePath: process.env.NUXT_PUBLIC_GENAI_IMAGE_PATH || "/api/genai/image",
			presentationsPath: process.env.NUXT_PUBLIC_PRESENTATIONS_PATH || "/api/presentations",
		},
	},
	shadcn: {
		/**
		 * Prefix for all the imported component.
		 * @default "Ui"
		 */
		prefix: "",
		/**
		 * Directory that the component lives in.
		 * Will respect the Nuxt aliases.
		 * @link https://nuxt.com/docs/api/nuxt-config#alias
		 * @default "@/components/ui"
		 */
		componentDir: "@/components/ui",
	},
})
