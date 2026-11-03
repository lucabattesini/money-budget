import { Flex, Box } from "@chakra-ui/react";
import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { getFamily } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { setLocale } from "../lib/locale";
import Header from "./Header";
import { Toaster } from "./ui/toaster";

export default function Layout() {
    // The family's currency and language, for every page. If they cannot be loaded the app keeps reais and Portuguese.
    useEffect(() => {
        const token = getToken();
        if (token) getFamily(token).then((result) => result.ok && setLocale(result.data));
    }, []);

    return (
        <Flex direction="column" h="100vh" w="100vw" overflow="hidden">
            <Header />
            <Toaster />
            <Box flex="1" overflowY="auto">
                <Outlet />
            </Box>
        </Flex>
    );
}
