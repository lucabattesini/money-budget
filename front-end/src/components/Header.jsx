import { Flex, Box, Link, Text, Icon } from "@chakra-ui/react";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { LuLayoutDashboard, LuReceipt, LuArrowRightLeft, LuUser } from "react-icons/lu";

export default function Header() {
    const location = useLocation();
    const currentPath = location.pathname;

    const navItems = [
        { name: "Dashboard", path: "/", icon: LuLayoutDashboard },
        { name: "Transactions", path: "/transactions", icon: LuArrowRightLeft },
        { name: "Report Expense", path: "/report-expense", icon: LuReceipt },
        { name: "Account", path: "/account", icon: LuUser },
    ];

    return (
        <Flex
            as="header"
            w="100%"
            h="60px"
            bg="transparent"
            color="white"
            px={8}
            align="center"
            justify="space-between"
        >
            <Box>
                <Text fontSize="xl" fontWeight="bold" color="white">
                    Money Budget
                </Text>
            </Box>

            <Flex gap={6} as="nav">
                {navItems.map((item) => {
                    const isActive = currentPath === item.path;
                    return (
                        <Link
                            key={item.name}
                            as={RouterLink}
                            to={item.path}
                            _hover={{ textDecoration: "none", color: "white" }}
                            color={isActive ? "white" : "gray.400"}
                            display="flex"
                            alignItems="center"
                            gap={2}
                            transition="all 0.2s"
                        >
                            <Icon as={item.icon} boxSize={4} />
                            <Text fontSize="sm" fontWeight={isActive ? "bold" : "medium"}>
                                {item.name}
                            </Text>
                        </Link>
                    );
                })}
            </Flex>
        </Flex>
    );
}
