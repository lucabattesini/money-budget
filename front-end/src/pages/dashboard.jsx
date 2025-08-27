import { Stack, Center, Heading, Box } from "@chakra-ui/react"
import BarListChart from "../utils/charts"
import Home from "./home"

export default function Dashboard() {
    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >
                <Box position="absolute" right={6} top={6}>
                    <Home/>
                </Box>
                <Heading size={"2xl"}>
                    Dashboard
                </Heading>
                <BarListChart/>
            </Stack>
        </Center>
    )
}