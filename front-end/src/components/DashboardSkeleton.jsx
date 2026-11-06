import { Grid, Skeleton, Stack, VisuallyHidden } from "@chakra-ui/react";

// What the dashboard looks like while it loads: grey boxes where the cards will be, so the page does not jump when the
// data arrives. Same grid as the dashboard.
export default function DashboardSkeleton() {
    return (
        <Grid templateColumns={{ base: "minmax(0, 1fr)", lg: "3fr 2fr" }} gap={6} alignItems="start" role="status" aria-busy="true">
            <VisuallyHidden>Carregando…</VisuallyHidden>
            <Stack gap={6}>
                <Skeleton height="160px" borderRadius="xl" />
                <Skeleton height="120px" borderRadius="xl" />
                <Skeleton height="280px" borderRadius="xl" />
            </Stack>
            <Stack gap={6}>
                <Skeleton height="320px" borderRadius="xl" />
                <Skeleton height="220px" borderRadius="xl" />
            </Stack>
        </Grid>
    );
}
