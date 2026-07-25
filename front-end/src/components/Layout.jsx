import { Flex, Box } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

export default function Layout() {
    return (
        <Flex h="100vh" w="100vw" overflow="hidden">
            <Sidebar />
            <Box flex="1" overflowY="auto">
                <Outlet />
            </Box>
        </Flex>
    );
}
