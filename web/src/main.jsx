import React from "react";
import ReactDOM from "react-dom/client";
import { MantineProvider } from "@mantine/core";
import { DatesProvider } from "@mantine/dates";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { theme, colorScheme } from "./theme";
import App from "./App";

import "@mantine/core/styles.css";
import "@mantine/dates/styles.css";
import "@mantine/notifications/styles.css";
import "./tui.css";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			refetchOnWindowFocus: false,
			retry: 1,
			staleTime: 30000,
		},
	},
});

ReactDOM.createRoot(document.getElementById("root")).render(
	<React.StrictMode>
		<QueryClientProvider client={queryClient}>
			<MantineProvider
				theme={theme}
				defaultColorScheme={colorScheme}
				forceColorScheme={colorScheme}
			>
				<Notifications position="top-right" />
				<DatesProvider settings={{ firstDayOfWeek: 1 }}>
					<BrowserRouter>
						<App />
					</BrowserRouter>
				</DatesProvider>
			</MantineProvider>
		</QueryClientProvider>
	</React.StrictMode>,
);
