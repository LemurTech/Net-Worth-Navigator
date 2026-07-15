// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://lemurtech.github.io',
	base: '/Net-Worth-Navigator',
	integrations: [
		starlight({
			title: 'Net Worth Navigator',
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/LemurTech/Net-Worth-Navigator' },
			],
			editLink: {
				baseUrl: 'https://github.com/LemurTech/Net-Worth-Navigator/edit/main/docs/guide',
			},
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Welcome', slug: 'getting-started' },
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Quick Start', slug: 'getting-started/quick-start' },
						{ label: 'Running the Web UI', slug: 'getting-started/running-the-web-ui' },
						{ label: 'Command Line Basics', slug: 'getting-started/command-line-basics' },
					],
				},
				{
					label: 'Key Concepts',
					items: [
						{ label: 'What Is a Scenario?', slug: 'key-concepts/scenario' },
						{ label: 'Understanding Your Projection', slug: 'key-concepts/projection' },
						{ label: 'Account Types Explained', slug: 'key-concepts/account-types' },
						{ label: 'Events & the Event System', slug: 'key-concepts/events' },
						{ label: 'Social Security Benefits', slug: 'key-concepts/social-security' },
						{ label: 'Render Modes', slug: 'key-concepts/render-modes' },
						{ label: 'Balance Updates & Start Year', slug: 'key-concepts/balance-updates' },
					],
				},
				{
					label: 'Data Sources',
					items: [
						{ label: 'Manual Entry (the Bucket Approach)', slug: 'data-sources/manual-entry' },
						{ label: 'CSV Import', slug: 'data-sources/csv-import' },
						{ label: 'Monarch Money (Live Sync)', slug: 'data-sources/monarch-money' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Using the Setup Panel', slug: 'guides/using-the-setup-panel' },
						{ label: 'Comparing Scenarios', slug: 'guides/comparing-scenarios' },
						{ label: 'Understanding Monte Carlo Analysis', slug: 'guides/understanding-monte-carlo' },
						{ label: 'Updating NWN', slug: 'guides/updating' },
						{ label: 'Running on a Home Web Server', slug: 'guides/home-server' },
						{ label: 'Troubleshooting', slug: 'guides/troubleshooting' },
						{ label: 'FAQ', slug: 'guides/faq' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Configuration Reference', slug: 'reference/configuration' },
						{ label: 'Event Types', slug: 'reference/event-types' },
						{ label: 'Installing Git for Windows', slug: 'reference/installing-git-windows' },
						{ label: 'Project Structure', slug: 'reference/project-structure' },
						{ label: 'License & Security', slug: 'reference/license' },
					],
				},
			],
		}),
	],
});
