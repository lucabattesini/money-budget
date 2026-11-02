import { Flex, Box } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import Header from "./Header";
import { Toaster } from "./ui/toaster";

export default function Layout() {
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
