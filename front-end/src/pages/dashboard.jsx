import { Stack, Center, Heading } from "@chakra-ui/react"
import BarListChart from "../utils/charts"

export default function Dashboard() {
    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size={"2xl"}>
                    Dashboard
                </Heading>
                <BarListChart/>
            </Stack>
        </Center>
    )
}