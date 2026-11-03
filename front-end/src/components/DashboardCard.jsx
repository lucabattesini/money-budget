import { Box, Heading, HStack, Link } from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";

// One card of the dashboard: a small title, an optional link to the full page and the content.
export default function DashboardCard({ title, to, linkText, children }) {
    return (
        <Box w="full" p={5} borderWidth="1px" borderRadius="xl" bg="bg.panel">
            <HStack justify="space-between" mb={4}>
                <Heading as="h2" size="sm" color="fg.muted" fontWeight="semibold">{title}</Heading>
                {to && <Link as={RouterLink} to={to} fontSize="sm">{linkText}</Link>}
            </HStack>
            {children}
        </Box>
    );
}
