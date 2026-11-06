import { Flex, Link, Text, Icon } from "@chakra-ui/react";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { LuLayoutDashboard, LuArrowRightLeft, LuPiggyBank, LuUser } from "react-icons/lu";

export default function Header() {
    const location = useLocation();
    const currentPath = location.pathname;

    const navItems = [
        { name: "Dashboard", path: "/", icon: LuLayoutDashboard },
        { name: "Transações", path: "/transactions", icon: LuArrowRightLeft },
        { name: "Orçamentos", path: "/budgets", icon: LuPiggyBank },
        { name: "Conta", path: "/account", icon: LuUser },
    ];

    return (
        <Flex
            as="header"
            w="100%"
            h="60px"
            bg={{ base: "gray.900", md: "transparent" }}
            color="white"
            px={{ base: 4, md: 8 }}
            align="center"
            justify="space-between"
        >
            <Link
                as={RouterLink}
                to="/"
                aria-label="Money Budget, ir para o início"
                _hover={{ textDecoration: "none" }}
                display="inline-flex"
                alignItems="center"
                minH="44px"
            >
                <Text fontSize="xl" fontWeight="bold" color="white">
                    Money Budget
                </Text>
            </Link>

            {/* A bar at the bottom of the screen on a phone (easy to reach with a thumb); in the header on larger screens */}
            <Flex
                as="nav"
                aria-label="Menu principal"
                gap={{ base: 0, md: 6 }}
                position={{ base: "fixed", md: "static" }}
                bottom={0}
                left={0}
                right={0}
                zIndex="sticky"
                bg={{ base: "gray.900", md: "transparent" }}
                borderTopWidth={{ base: "1px", md: 0 }}
                borderColor="gray.700"
                pb={{ base: "env(safe-area-inset-bottom)", md: 0 }}
            >
                {navItems.map((item) => {
                    // "/" only matches itself; other entries also match their sub-pages (/account/data)
                    const isActive = item.path === "/" ? currentPath === "/" : currentPath.startsWith(item.path);
                    return (
                        <Link
                            key={item.name}
                            as={RouterLink}
                            to={item.path}
                            aria-current={isActive ? "page" : undefined}
                            _hover={{ textDecoration: "none", color: "white" }}
                            color={isActive ? "white" : "gray.400"}
                            display="flex"
                            flexDirection={{ base: "column", md: "row" }}
                            alignItems="center"
                            justifyContent="center"
                            flex={{ base: 1, md: "initial" }}
                            minH={{ base: "60px", md: "auto" }}
                            gap={{ base: 1, md: 2 }}
                            transition="all 0.2s"
                        >
                            <Icon as={item.icon} boxSize={4} />
                            <Text fontSize={{ base: "xs", md: "sm" }} fontWeight={isActive ? "bold" : "medium"}>
                                {item.name}
                            </Text>
                        </Link>
                    );
                })}
            </Flex>
        </Flex>
    );
}
